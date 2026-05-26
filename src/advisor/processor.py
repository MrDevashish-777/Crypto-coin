"""AdvisorProcessor — CoinDCX live data → SOP signal → PDF."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from config.constants import CRYPTO_PAIRS
from config.settings import settings
from src.advisor.allocation import WeeklyAllocationTracker
from src.advisor.narrative import generate_narrative
from src.advisor.persistence import (
    close_advisor_signals,
    load_weekly_publish_records,
    persist_advisor_signal,
)
from src.advisor.schemas import AdvisorSignal
from src.advisor.sop_gates import validate_levels
from src.advisor.targets import compute_advisor_levels
from src.advisor.validity import compute_valid_until, infer_trade_horizon, now_ist
from src.data.data_fetcher import DataFetcher
from src.llm.agent import LLMAgentFactory
from src.planitt.confluence import ConfluenceFeatures, evaluate_confluence_pre_gates_with_reason
from src.planitt.mtf_confluence import check_htf_alignment, higher_timeframes_for

logger = logging.getLogger(__name__)


class AdvisorProcessor:
    """Production pipeline for CoinDCX futures advisor PDF signals."""

    def __init__(self, margin_currency: str | None = None) -> None:
        self.margin_currency = (margin_currency or settings.COINDCX_DEFAULT_MARGIN).upper()
        self.data_fetcher = DataFetcher(margin_currency=self.margin_currency)
        self.allocation = WeeklyAllocationTracker()
        self._allocation_loaded = False
        self.llm_agent = None
        if settings.ENABLE_LLM_ANALYSIS:
            try:
                self.llm_agent = LLMAgentFactory.create_agent(
                    provider=settings.LLM_PROVIDER,
                    api_key=getattr(settings, f"{settings.LLM_PROVIDER.upper()}_API_KEY", None),
                    model=getattr(settings, f"{settings.LLM_PROVIDER.upper()}_MODEL", None),
                    base_url=settings.OLLAMA_BASE_URL if settings.LLM_PROVIDER == "ollama" else None,
                )
            except Exception as exc:
                logger.warning("LLM agent unavailable: %s", exc)

    async def _ensure_allocation(self) -> None:
        if self._allocation_loaded:
            return
        try:
            records = await load_weekly_publish_records()
            self.allocation.hydrate(records)
        except Exception as exc:
            logger.warning("Could not hydrate allocation from DB: %s", exc)
        self._allocation_loaded = True

    async def _fetch_htf_candles(self, symbol: str, signal_tf: str) -> dict[str, Any]:
        min_candles = max(settings.PLANITT_MIN_CANDLES, 205)
        htf_data: dict[str, Any] = {}
        for tf in higher_timeframes_for(signal_tf):
            try:
                htf_data[tf] = await self.data_fetcher.fetch_candles(
                    symbol,
                    tf,
                    limit=min_candles + 20,
                    from_cache=True,
                    min_candles=min_candles,
                )
            except Exception as exc:
                logger.warning("HTF fetch failed %s %s: %s", symbol, tf, exc)
        return htf_data

    @staticmethod
    def _composite_score(features: ConfluenceFeatures) -> float:
        return features.pre_confidence + (features.mtf_score * 0.15)

    async def generate_signal(
        self,
        symbol: str,
        timeframe: str,
        *,
        force: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Run full pipeline; returns result dict with signal or reject_reason."""
        await self._ensure_allocation()

        if symbol not in CRYPTO_PAIRS:
            return {"ok": False, "reject_reason": f"unsupported_symbol:{symbol}"}

        if not dry_run:
            can_pub, alloc_reason = self.allocation.can_publish(symbol)
            if not can_pub and not force:
                return {"ok": False, "reject_reason": alloc_reason}

        pair = self.data_fetcher.pair_for_symbol(symbol, self.margin_currency)
        min_candles = max(settings.PLANITT_MIN_CANDLES, 205)

        try:
            candle_list = await self.data_fetcher.fetch_candles(
                symbol,
                timeframe,
                limit=min_candles + 20,
                from_cache=dry_run,
                min_candles=min_candles,
            )
            live_price = await self.data_fetcher.get_current_price(symbol, self.margin_currency)
            try:
                await close_advisor_signals(symbol, live_price)
            except Exception as exc:
                logger.debug("Outcome closure skipped for %s: %s", symbol, exc)
        except Exception as exc:
            logger.warning("Data fetch failed for %s: %s", symbol, exc)
            return {"ok": False, "reject_reason": f"data_error:{exc}"}

        evaluation = evaluate_confluence_pre_gates_with_reason(
            candle_list,
            adx_trend_threshold=settings.PLANITT_ADX_TREND_THRESHOLD,
            volume_multiplier=settings.PLANITT_VOLUME_MULTIPLIER,
            touch_tolerance_pct=settings.PLANITT_TOUCH_TOLERANCE_PCT,
            min_confluence_hits=settings.ADVISOR_MIN_CONFLUENCE_HITS,
        )
        if evaluation.features is None:
            return {"ok": False, "reject_reason": evaluation.reject_reason}

        features = evaluation.features
        htf_candles = await self._fetch_htf_candles(symbol, timeframe)
        mtf = check_htf_alignment(features.side, timeframe, htf_candles)
        if not mtf.aligned:
            return {"ok": False, "reject_reason": mtf.reject_reason}

        features = replace(features, mtf_score=mtf.mtf_score)

        if features.pre_confidence < settings.ADVISOR_MIN_CONFIDENCE:
            return {
                "ok": False,
                "reject_reason": f"confidence_{features.pre_confidence:.2f}",
            }

        levels = compute_advisor_levels(features, candle_list=candle_list)
        sop = validate_levels(
            direction=features.side,
            entry_low=float(levels["entry_low"]),
            entry_high=float(levels["entry_high"]),
            stop_loss=float(levels["stop_loss"]),
            target=float(levels["target"]),
            live_price=live_price,
            sl_pct=float(levels["sl_pct"]),
            tp_pct=float(levels["tp_pct"]),
            leverage=float(levels["leverage"]),
            risk_reward=str(levels["risk_reward"]),
            confidence=features.pre_confidence,
        )
        if not sop.ok:
            return {"ok": False, "reject_reason": sop.reason}

        composite_score = self._composite_score(features)
        if dry_run:
            return {
                "ok": True,
                "composite_score": composite_score,
                "features": features,
                "levels": levels,
                "live_price": live_price,
                "pair": pair,
                "candle_list": candle_list,
            }

        why, entry_reason, monitor = await generate_narrative(
            features,
            pair=pair,
            levels=levels,
            llm_agent=self.llm_agent,
        )

        trade_horizon = infer_trade_horizon(timeframe)
        generated_at = datetime.now(timezone.utc)
        valid_until = compute_valid_until(trade_horizon, generated_at=now_ist())

        signal = AdvisorSignal(
            pair=pair,
            symbol=symbol.upper(),
            margin_currency=self.margin_currency,
            direction=features.side,
            trade_horizon=trade_horizon,
            timeframe=timeframe,
            entry_low=float(levels["entry_low"]),
            entry_high=float(levels["entry_high"]),
            stop_loss=float(levels["stop_loss"]),
            target=float(levels["target"]),
            sl_pct=float(levels["sl_pct"]),
            tp_pct=float(levels["tp_pct"]),
            leverage=float(levels["leverage"]),
            risk_reward=str(levels["risk_reward"]),
            confidence=features.pre_confidence,
            valid_until_ist=valid_until,
            generated_at=generated_at,
            live_price_at_signal=live_price,
            indicators=list(levels.get("chart_indicators", []))[:2],
            setup_type=features.setup_type,
            confluence_hits=list(features.confluence_hits),
            reason_why_token=why,
            reason_entry=entry_reason,
            reason_monitor=monitor,
        )

        from src.reports.pdf_report import generate_advisor_pdf

        pdf_path, chart_path = await generate_advisor_pdf(signal, candle_list)
        signal.pdf_path = str(pdf_path)
        signal.chart_path = str(chart_path)

        try:
            await persist_advisor_signal(signal)
        except Exception as exc:
            logger.warning("Mongo persist failed: %s", exc)

        if not force:
            self.allocation.record(symbol)

        return {
            "ok": True,
            "composite_score": composite_score,
            "signal": signal.model_dump(mode="json"),
            "pdf_path": signal.pdf_path,
            "chart_path": signal.chart_path,
        }

    async def scan_universe(
        self,
        symbols: list[str] | None = None,
        timeframes: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Scan symbols × timeframes; publish highest-scoring candidate per symbol."""
        await self._ensure_allocation()
        syms = symbols or list(CRYPTO_PAIRS.keys())
        tfs = timeframes or settings.advisor_scan_timeframes
        results: list[dict[str, Any]] = []
        best_by_symbol: dict[str, tuple[float, str, dict[str, Any]]] = {}
        reject_counts: dict[str, int] = {}

        for tf in tfs:
            for sym in syms:
                out = await self.generate_signal(sym, tf, dry_run=True)
                results.append({"symbol": sym, "timeframe": tf, "phase": "candidate", **out})
                if not out.get("ok"):
                    reason = str(out.get("reject_reason", "unknown")).split(":")[0]
                    reject_counts[reason] = reject_counts.get(reason, 0) + 1
                    continue
                score = float(out.get("composite_score", 0.0))
                prev = best_by_symbol.get(sym)
                if prev is None or score > prev[0]:
                    best_by_symbol[sym] = (score, tf, out)

        ranked = sorted(
            ((sym, score, tf, out) for sym, (score, tf, out) in best_by_symbol.items()),
            key=lambda item: item[1],
            reverse=True,
        )

        published = 0
        for sym, _score, tf, _out in ranked:
            recent = self.allocation.recent_publishes()
            if len(recent) >= settings.MAX_WEEKLY_SIGNALS:
                logger.info("Weekly cap reached (%d)", settings.MAX_WEEKLY_SIGNALS)
                break
            can_pub, reason = self.allocation.can_publish(sym)
            if not can_pub:
                logger.info("Skipped publish for %s %s: %s", sym, tf, reason or "allocation_blocked")
                continue
            pub = await self.generate_signal(sym, tf)
            results.append({"symbol": sym, "timeframe": tf, "phase": "publish", **pub})
            if pub.get("ok"):
                published += 1
                logger.info("Published advisor signal %s %s (ranked scan)", sym, tf)
            else:
                logger.info(
                    "Skipped publish for %s %s: %s",
                    sym,
                    tf,
                    pub.get("reject_reason", "unknown"),
                )

        logger.info("Scan complete: %d published from %d candidates", published, len(ranked))
        if reject_counts:
            top = sorted(reject_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            logger.info("Candidate rejects (top): %s", ", ".join(f"{k}={v}" for k, v in top))
        if not ranked and reject_counts:
            top = sorted(reject_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            logger.info(
                "No candidates passed filters. Top reject reasons: %s",
                ", ".join(f"{k}={v}" for k, v in top),
            )
            near_miss: list[tuple[float, str, str, str]] = []
            for r in results:
                if r.get("ok"):
                    continue
                score_raw = r.get("composite_score")
                if score_raw is None:
                    continue
                near_miss.append(
                    (float(score_raw), str(r.get("symbol", "")), str(r.get("timeframe", "")), str(r.get("reject_reason", ""))),
                )
            if near_miss:
                best = max(near_miss, key=lambda x: x[0])
                logger.info(
                    "Closest near-miss: %s %s score=%.3f reason=%s",
                    best[1],
                    best[2],
                    best[0],
                    best[3],
                )
        return results

    async def close(self) -> None:
        await self.data_fetcher.close()
