"""AdvisorProcessor — CoinDCX live data → SOP signal → PDF."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any
import asyncio

from config.constants import CRYPTO_PAIRS
from config.settings import settings
from src.advisor.allocation import WeeklyAllocationTracker
from src.advisor.narrative import generate_narrative
from src.advisor.persistence import (
    close_advisor_signals,
    load_weekly_publish_records,
    persist_advisor_signal,
    has_open_advisor_signal,
)
from src.advisor.schemas import AdvisorSignal
from src.advisor.macro_trend import validate_macro_for_signal
from src.advisor.segment_gates import (
    get_publish_thresholds,
    mtf_min_agreeing_for,
    passes_segment_quality,
    validate_tier_a,
)
from src.advisor.live_performance import passes_live_bucket
from src.advisor.reachability import ReachabilityResult, reachability_from_levels
from src.advisor.sop_gates import validate_levels
from src.advisor.targets import compute_advisor_levels
from src.advisor.validity import compute_valid_until, infer_trade_horizon, now_ist
from src.data.data_fetcher import DataFetcher
from src.llm.agent import LLMAgentFactory
from src.analysis.backtest_config import get_bucket_expectancy, quality_tier
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

    async def _fetch_btc_htf(self, signal_tf: str) -> dict[str, Any]:
        """BTC 4h/1d for macro SELL guard on alts."""
        out: dict[str, Any] = {}
        for tf in ("4h", "1d"):
            try:
                out[tf] = await self.data_fetcher.fetch_candles(
                    "BTC",
                    tf,
                    limit=max(settings.PLANITT_MIN_CANDLES, 205) + 20,
                    from_cache=True,
                    min_candles=max(settings.PLANITT_MIN_CANDLES, 205),
                )
            except Exception as exc:
                logger.warning("BTC HTF fetch failed %s: %s", tf, exc)
        return out

    @staticmethod
    def _rank_score(composite: float, side: str) -> float:
        """Prefer BUY intraday — demote SELL in ranking."""
        score = composite
        if side == "BUY":
            score += 0.12
        else:
            score -= 0.08
        return score

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
        return features.pre_confidence + (features.mtf_score * settings.ADVISOR_MTF_SCORE_WEIGHT)

    def _passes_direction_and_universe(
        self,
        symbol: str,
        timeframe: str,
        direction: str,
    ) -> tuple[bool, str | None]:
        if timeframe in settings.advisor_blocked_timeframes:
            return False, f"timeframe_blocked_{timeframe}"
        allowlist = settings.advisor_symbol_allowlist
        if allowlist is not None and symbol.upper() not in allowlist:
            return False, f"symbol_not_in_allowlist_{symbol}"
        if direction.upper() not in settings.advisor_allowed_directions:
            return False, f"direction_blocked_{direction}"
        return True, None

    def _passes_publish_quality(
        self,
        features: ConfluenceFeatures,
        composite_score: float,
        tier: str,
        symbol: str,
        timeframe: str,
        *,
        reach: ReachabilityResult | None = None,
        risk_reward_value: float = 0.0,
    ) -> tuple[bool, str | None]:
        ok_seg, seg_reason = passes_segment_quality(
            features=features,
            composite_score=composite_score,
            tier=tier,
            timeframe=timeframe,
        )
        if not ok_seg:
            return False, seg_reason

        ok_tier_a, tier_a_reason = validate_tier_a(
            tier=tier,
            direction=features.side,
            timeframe=timeframe,
            features=features,
            mtf_score=features.mtf_score,
            reach=reach or ReachabilityResult(True, None, 0, 0, "intraday", 0),
            risk_reward_value=risk_reward_value,
        )
        if not ok_tier_a:
            return False, tier_a_reason

        profile = get_publish_thresholds(features.side, timeframe)
        if profile.require_swing_reachability and reach is not None:
            if reach.trade_horizon != "swing" or not reach.ok:
                return False, reach.reason or "swing_reachability_failed"
        if settings.ADVISOR_BLOCK_NEGATIVE_BUCKETS:
            bucket_exp = get_bucket_expectancy(symbol, timeframe, direction=features.side)
            if bucket_exp is not None and bucket_exp < 0:
                return False, f"negative_bucket_{bucket_exp:.3f}"
        if settings.ADVISOR_BACKTEST_QUALITY_GATE_ENABLED:
            bucket_exp = get_bucket_expectancy(symbol, timeframe, direction=features.side)
            if bucket_exp is not None and bucket_exp < settings.ADVISOR_BACKTEST_MIN_EXPECTANCY:
                return False, f"backtest_bucket_expectancy_{bucket_exp:.3f}"
        if settings.ADVISOR_LIVE_PERFORMANCE_GATE_ENABLED:
            ok_live, live_reason = passes_live_bucket(
                symbol,
                timeframe,
                direction=features.side,
                min_expectancy=settings.ADVISOR_LIVE_MIN_BUCKET_EXPECTANCY,
                min_trades=settings.ADVISOR_LIVE_MIN_BUCKET_TRADES,
            )
            if not ok_live:
                return False, live_reason
        return True, None

    async def generate_signal(
        self,
        symbol: str,
        timeframe: str,
        *,
        force: bool = False,
        dry_run: bool = False,
        btc_htf: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run full pipeline; returns result dict with signal or reject_reason."""
        await self._ensure_allocation()

        if symbol not in CRYPTO_PAIRS:
            return {"ok": False, "reject_reason": f"unsupported_symbol:{symbol}"}

        if not dry_run:
            from src.advisor.macro_calendar import macro_calendar
            is_blackout, blackout_reason = await macro_calendar.is_blackout_active()
            if is_blackout and not force:
                return {"ok": False, "reject_reason": f"macro_blackout:{blackout_reason}"}

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
                await close_advisor_signals(
                    symbol, live_price, candle_list=candle_list, fetcher=self.data_fetcher
                )
            except Exception as exc:
                logger.debug("Outcome closure skipped for %s: %s", symbol, exc)
        except Exception as exc:
            logger.warning("Data fetch failed for %s: %s", symbol, exc)
            return {"ok": False, "reject_reason": f"data_error:{exc}"}

        if not force:
            if await has_open_advisor_signal(symbol, timeframe):
                return {"ok": False, "reject_reason": "active_open_signal_exists"}

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
        profile = get_publish_thresholds(features.side, timeframe)
        htf_candles = await self._fetch_htf_candles(symbol, timeframe)
        mtf = check_htf_alignment(
            features.side,
            timeframe,
            htf_candles,
            strict=profile.strict_htf,
            min_agree_override=mtf_min_agreeing_for(features.side, timeframe),
        )
        if not mtf.aligned:
            return {"ok": False, "reject_reason": mtf.reject_reason}

        features = replace(features, mtf_score=mtf.mtf_score)

        macro_btc = btc_htf
        if macro_btc is None and symbol.upper() != "BTC" and (
            features.side == "SELL"
            or (features.side == "BUY" and settings.ADVISOR_REQUIRE_BTC_BULL_FOR_BUY)
        ):
            macro_btc = await self._fetch_btc_htf(timeframe)
        ok_macro, macro_reason = validate_macro_for_signal(
            symbol=symbol.upper(),
            side=features.side,
            timeframe=timeframe,
            signal_ts_ms=candle_list.candles[-1].timestamp,
            btc_htf=macro_btc,
        )
        if not ok_macro and not force:
            return {"ok": False, "reject_reason": macro_reason}

        ok_universe, universe_reason = self._passes_direction_and_universe(
            symbol, timeframe, features.side
        )
        if not ok_universe and not force:
            return {"ok": False, "reject_reason": universe_reason}

        if features.pre_confidence < profile.min_confidence:
            return {
                "ok": False,
                "reject_reason": f"confidence_{features.pre_confidence:.2f}",
            }

        levels = compute_advisor_levels(features, candle_list=candle_list, live_price=live_price)
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

        generated_at_ist = now_ist()
        reach = reachability_from_levels(
            levels,
            atr=float(features.atr or live_price * 0.0008),
            price=live_price,
            timeframe=timeframe,
            generated_at=generated_at_ist,
        )
        if not reach.ok and not force:
            return {"ok": False, "reject_reason": reach.reason}

        trade_horizon = reach.trade_horizon
        if settings.ADVISOR_BLOCK_SWING_HORIZON and trade_horizon == "swing" and not force:
            return {"ok": False, "reject_reason": "swing_horizon_blocked"}
        valid_until_preview = compute_valid_until(
            trade_horizon, generated_at=generated_at_ist, timeframe=timeframe
        )

        composite_score = self._composite_score(features)
        tier = quality_tier(composite_score)
        try:
            rr_val = float(str(levels["risk_reward"]).split(":", 1)[1])
        except (IndexError, ValueError):
            rr_val = 0.0
        ok_quality, quality_reason = self._passes_publish_quality(
            features,
            composite_score,
            tier,
            symbol,
            timeframe,
            reach=reach,
            risk_reward_value=rr_val,
        )
        if not ok_quality and not force:
            return {"ok": False, "reject_reason": quality_reason}
        if dry_run:
            return {
                "ok": True,
                "composite_score": composite_score,
                "quality_tier": tier,
                "features": features,
                "levels": levels,
                "live_price": live_price,
                "pair": pair,
                "trade_horizon": trade_horizon,
                "reachability": {
                    "tp_distance_pct": round(reach.tp_distance_pct, 3),
                    "expected_move_pct": round(reach.expected_move_pct, 3),
                },
                "candle_list": candle_list,
            }

        why, entry_reason, monitor = await generate_narrative(
            features,
            pair=pair,
            levels=levels,
            llm_agent=self.llm_agent,
        )

        trade_horizon = reach.trade_horizon
        generated_at = datetime.now(timezone.utc)
        valid_until = valid_until_preview

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
            composite_score=composite_score,
            quality_tier=tier,
            reason_why_token=why,
            reason_entry=entry_reason,
            reason_monitor=monitor,
        )

        from src.reports.pdf_report import generate_advisor_pdf

        pdf_path, chart_path = await generate_advisor_pdf(signal, candle_list)
        signal.pdf_path = str(pdf_path)
        signal.chart_path = str(chart_path)

        if settings.CLOUDINARY_URL:
            try:
                import os
                import asyncio
                os.environ["CLOUDINARY_URL"] = settings.CLOUDINARY_URL
                import cloudinary
                import cloudinary.uploader
                cloudinary.reset_config()
                
                upload_res = await asyncio.to_thread(
                    cloudinary.uploader.upload,
                    str(pdf_path),
                    resource_type="raw",
                    format="pdf",
                )
                signal.cloudinary_pdf_url = upload_res.get("secure_url")
                logger.info("Cloudinary PDF uploaded: %s", signal.cloudinary_pdf_url)
            except Exception as exc:
                logger.warning("Cloudinary PDF upload failed: %s", exc)

        try:
            await persist_advisor_signal(signal)
        except Exception as exc:
            logger.warning("Mongo persist failed: %s", exc)

        if not force:
            self.allocation.record(symbol, timeframe=timeframe)

        # Trigger Delta Exchange Execution
        try:
            from src.execution.executor import executor
            await executor.execute_signal(signal)
        except Exception as exc:
            logger.error("Delta Execution hook failed: %s", exc)

        return {
            "ok": True,
            "composite_score": composite_score,
            "signal": signal.model_dump(mode="json"),
            "pdf_path": signal.pdf_path,
            "chart_path": signal.chart_path,
        }

    def _ordered_scan_symbols(self, symbols: list[str]) -> list[str]:
        priority = settings.advisor_publish_priority_symbols
        priority_set = set(priority)
        ordered = [s for s in priority if s in symbols]
        ordered.extend(s for s in symbols if s not in priority_set)
        return ordered

    async def scan_universe(
        self,
        symbols: list[str] | None = None,
        timeframes: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Scan symbols × timeframes; publish top candidates up to daily/per-scan caps."""
        await self._ensure_allocation()
        syms = self._ordered_scan_symbols(symbols or list(CRYPTO_PAIRS.keys()))
        allowlist = settings.advisor_symbol_allowlist
        if allowlist is not None:
            syms = [s for s in syms if s.upper() in allowlist]
        tfs = timeframes or settings.advisor_scan_timeframes
        results: list[dict[str, Any]] = []
        candidates: list[tuple[float, str, str, dict[str, Any]]] = []
        reject_counts: dict[str, int] = {}
        btc_htf = await self._fetch_btc_htf("")

        for tf in tfs:
            for sym in syms:
                out = await self.generate_signal(sym, tf, dry_run=True, btc_htf=btc_htf)
                results.append({"symbol": sym, "timeframe": tf, "phase": "candidate", **out})
                if not out.get("ok"):
                    reason = str(out.get("reject_reason", "unknown")).split(":")[0]
                    reject_counts[reason] = reject_counts.get(reason, 0) + 1
                    continue
                features = out.get("features")
                side = features.side if features is not None else "BUY"
                score = self._rank_score(float(out.get("composite_score", 0.0)), side)
                candidates.append((score, sym, tf, out))

        ranked = sorted(candidates, key=lambda item: item[0], reverse=True)

        daily_remaining = self.allocation.daily_slots_remaining()
        daily_count = self.allocation.daily_publish_count()
        if daily_count < settings.ADVISOR_TARGET_DAILY_SIGNALS:
            # Aggressive fill when below daily target
            per_scan_limit = min(
                daily_remaining,
                max(settings.MAX_PUBLISH_PER_SCAN, settings.ADVISOR_TARGET_DAILY_SIGNALS - daily_count),
            )
        else:
            per_scan_limit = min(settings.MAX_PUBLISH_PER_SCAN, daily_remaining)
        if per_scan_limit <= 0:
            logger.info(
                "Daily cap reached (%d/%d); skipping publish phase",
                self.allocation.daily_publish_count(),
                settings.MAX_DAILY_SIGNALS,
            )
            return results

        published = 0
        published_keys: set[tuple[str, str]] = set()
        for _score, sym, tf, _out in ranked:
            if published >= per_scan_limit:
                break
            key = (sym, tf)
            if key in published_keys:
                continue
            if self.allocation.daily_slots_remaining() <= 0:
                logger.info("Daily cap reached during scan")
                break
            can_pub, reason = self.allocation.can_publish(sym)
            if not can_pub:
                logger.info("Skipped publish for %s %s: %s", sym, tf, reason or "allocation_blocked")
                continue
            pub = await self.generate_signal(sym, tf, btc_htf=btc_htf)
            results.append({"symbol": sym, "timeframe": tf, "phase": "publish", **pub})
            if pub.get("ok"):
                published += 1
                published_keys.add(key)
                logger.info("Published advisor signal %s %s (ranked scan)", sym, tf)
            else:
                logger.info(
                    "Skipped publish for %s %s: %s",
                    sym,
                    tf,
                    pub.get("reject_reason", "unknown"),
                )

        daily_count = self.allocation.daily_publish_count()
        logger.info(
            "Scan complete: %d published from %d candidates (daily %d/%d, target %d)",
            published,
            len(ranked),
            daily_count,
            settings.MAX_DAILY_SIGNALS,
            settings.ADVISOR_TARGET_DAILY_SIGNALS,
        )
        if daily_count < settings.ADVISOR_TARGET_DAILY_SIGNALS:
            logger.info(
                "Below daily target (%d/%d) — top reject reasons may need further tuning",
                daily_count,
                settings.ADVISOR_TARGET_DAILY_SIGNALS,
            )
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
