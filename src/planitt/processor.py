from __future__ import annotations

import asyncio
import logging
import random
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from config.constants import CRYPTO_PAIRS, TIMEFRAMES
from config.settings import settings
from src.database.db import get_db
from src.data.data_fetcher import DataFetcher
from src.llm.agent import LLMAgentFactory
from src.llm.context import ContextManager
from src.planitt.confluence import evaluate_confluence_pre_gates_with_reason
from src.planitt.schemas import (
    PlanittSignal,
    compute_expires_at,
    now_utc,
    parse_planitt_llm_decision,
)
from src.planitt.mongo_collections import crypto_signal_find_filter, crypto_signals_collection
from src.planitt.persistence import (
    build_signal_document,
    close_completed_signals,
    get_symbol_news_sentiment,
    persist_signal_document,
)
from src.planitt.targets import compute_planitt_targets

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.ai_verifier import get_shared_verifier

logger = logging.getLogger(__name__)


def timeframe_to_cycle_seconds(timeframe: str) -> int:
    # Binance format timeframes supported in config/constants.py
    mapping = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "4h": 14400,
        "1d": 86400,
        "1w": 604800,
        "1M": 2592000,
    }
    return mapping.get(timeframe, 900)


class PlanittProcessor:
    """
    Planitt processor pipeline:
    pre-gates -> Ollama decision -> deterministic tp/sl -> validate -> POST to NestJS.
    """

    def __init__(self) -> None:
        self.data_fetcher = DataFetcher()
        self.context_manager = ContextManager()

        self.llm_agent = LLMAgentFactory.create_agent(
            provider=settings.LLM_PROVIDER,
            api_key=getattr(settings, f"{settings.LLM_PROVIDER.upper()}_API_KEY", None),
            model=getattr(settings, f"{settings.LLM_PROVIDER.upper()}_MODEL", None),
            base_url=settings.OLLAMA_BASE_URL if settings.LLM_PROVIDER == "ollama" else None,
        )

        self._dedup: dict[str, bool] = {}
        self._dedup_lock = asyncio.Lock()
        self._calibration_model = Pipeline(
            [
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(max_iter=300)),
            ]
        )
        self._calibration_fitted = False
        self.verifier = get_shared_verifier()

    async def close(self) -> None:
        await self.data_fetcher.close()

    def _dedup_key(self, *, asset: str, timeframe: str, created_at: datetime) -> str:
        # Keep a single active signal document per asset+timeframe so repeated
        # generations update the existing card instead of creating duplicates.
        _ = created_at  # maintained in signature for caller compatibility
        return f"{asset}:{timeframe}"

    async def generate_and_forward(
        self,
        *,
        symbol: str,
        timeframe: str,
        correlation_id: str,
    ) -> Optional[dict[str, Any]]:
        """
        Returns the payload forwarded to backend, or None if dropped as NO TRADE.
        """

        if symbol not in CRYPTO_PAIRS:
            return None
        if timeframe not in TIMEFRAMES:
            return None

        pair_asset = CRYPTO_PAIRS[symbol]

        created_at = now_utc()
        dedup_key = self._dedup_key(asset=pair_asset, timeframe=timeframe, created_at=created_at)
        async with self._dedup_lock:
            if dedup_key in self._dedup:
                logger.info(
                    "Planitt drop: duplicate",
                    extra={"correlation_id": correlation_id, "asset": pair_asset, "timeframe": timeframe},
                )
                return None
            # Reserve the key early to avoid concurrency duplicates.
            self._dedup[dedup_key] = True

        try:
            # 1) Fetch candles
            candle_list = await self.data_fetcher.fetch_candles(
                symbol=symbol,
                timeframe=timeframe,
                limit=260,
                from_cache=True,
                min_candles=settings.PLANITT_MIN_CANDLES,
            )

            # 2) Pre-gates (confluence)
            eval_result = evaluate_confluence_pre_gates_with_reason(
                candle_list,
                adx_trend_threshold=settings.PLANITT_ADX_TREND_THRESHOLD,
                volume_multiplier=settings.PLANITT_VOLUME_MULTIPLIER,
                touch_tolerance_pct=settings.PLANITT_TOUCH_TOLERANCE_PCT,
                min_confluence_hits=settings.PLANITT_MIN_CONFLUENCE_HITS,
            )
            features = eval_result.features
            if features is None:
                logger.info(
                    "Planitt drop: confluence_failed",
                    extra={
                        "correlation_id": correlation_id,
                        "asset": pair_asset,
                        "timeframe": timeframe,
                        "reason": eval_result.reject_reason,
                    },
                )
                async with self._dedup_lock:
                    self._dedup.pop(dedup_key, None)
                return None

            # 2b) Anti-whipsaw cooldown and trend persistence
            if await self._is_in_cooldown(symbol=symbol, timeframe=timeframe):
                logger.info(
                    "Planitt drop: cooldown_active",
                    extra={"correlation_id": correlation_id, "asset": pair_asset, "timeframe": timeframe},
                )
                async with self._dedup_lock:
                    self._dedup.pop(dedup_key, None)
                return None

            # 3) LLM decision (Ollama)
            market_data_for_llm = self._build_llm_input(features, candle_list)
            context = ""  # keep deterministic and avoid coupling to trade history for now
            if hasattr(self.context_manager, "get_market_regime_context"):
                context = self.context_manager.get_market_regime_context()

            decision_raw = None
            if hasattr(self.llm_agent, "generate_planitt_decision"):
                try:
                    decision_raw = await self.llm_agent.generate_planitt_decision(
                        market_data=market_data_for_llm,
                        context=context,
                    )
                except Exception as llm_exc:
                    logger.warning(
                        "LLM decision unavailable, using deterministic fallback",
                        extra={"correlation_id": correlation_id, "asset": pair_asset, "error": str(llm_exc)},
                    )
            else:
                logger.warning("LLM provider missing Planitt decision API; using deterministic fallback")

            parsed_decision = parse_planitt_llm_decision(decision_raw) if decision_raw is not None else None
            if parsed_decision is None or parsed_decision.model is None:
                fallback_decision = self._fallback_decision(features)
                if fallback_decision is None:
                    logger.info(
                        "Planitt drop: no_trade_after_fallback",
                        extra={
                            "correlation_id": correlation_id,
                            "asset": pair_asset,
                            "timeframe": timeframe,
                            "reason": None if parsed_decision is None else parsed_decision.dropped_reason,
                        },
                    )
                    async with self._dedup_lock:
                        self._dedup.pop(dedup_key, None)
                    return None
                decision = fallback_decision
            else:
                decision = parsed_decision.model
            decision_signal_type = str(getattr(decision, "signal_type", features.side) or features.side).upper()
            feature_signal_type = str(features.side).upper()
            disagreement_penalty = 0.0
            if decision_signal_type != feature_signal_type:
                # Deterministic technical side is the source of truth.
                disagreement_penalty = 0.08
                decision_signal_type = feature_signal_type
            if decision.confidence < settings.PLANITT_MIN_CONFIDENCE:
                logger.info(
                    "Planitt drop: confidence_below_threshold",
                    extra={"correlation_id": correlation_id, "asset": pair_asset, "timeframe": timeframe, "confidence": decision.confidence},
                )
                async with self._dedup_lock:
                    self._dedup.pop(dedup_key, None)
                return None

            # 4) Deterministic numeric levels
            targets = compute_planitt_targets(features)
            news_sentiment = await get_symbol_news_sentiment(symbol)
            confidence_prob = self._normalize_confidence(decision.confidence)
            confidence_prob = self._apply_news_adjustment(confidence_prob, decision_signal_type, news_sentiment)
            if disagreement_penalty > 0:
                confidence_prob = max(0.0, confidence_prob - disagreement_penalty)
            calibrated_conf = await self._calibrated_confidence(features, confidence_prob, news_sentiment)

            # 5) Assemble strict Planitt payload for validation
            planitt_signal = PlanittSignal.model_validate(
                {
                    "asset": pair_asset,
                    "signal_type": decision_signal_type,
                    "entry_range": targets["entry_range"],
                    "stop_loss": targets["stop_loss"],
                    "take_profit": targets["take_profit"],
                    "risk_reward_ratio": targets["risk_reward_ratio"],
                    "confidence": int(round(calibrated_conf * 100)),
                    "timeframe": timeframe,
                    "strategy": decision.strategy,
                    "reason": (
                        f"{decision.reason} | news_sentiment={news_sentiment:.2f}"
                        f"{' | llm_side_disagreement_penalty_applied' if disagreement_penalty > 0 else ''}"
                    ),
                    "validity": decision.validity,
                }
            )

            expires_at = compute_expires_at(created_at, planitt_signal.validity)
            reason_suffix = ""
            if features.candlestick_pattern:
                reason_suffix = (
                    f" | pattern={features.candlestick_pattern}"
                    f" strength={features.candlestick_strength:.2f}"
                    f" confirmed={features.candlestick_confirmed}"
                )
            payload = {
                "asset": planitt_signal.asset,
                "signal_type": planitt_signal.signal_type,
                "entry_range": planitt_signal.entry_range,
                "stop_loss": planitt_signal.stop_loss,
                "take_profit": planitt_signal.take_profit.model_dump(),
                "timeframe": planitt_signal.timeframe,
                "confidence": calibrated_conf,
                "strategy": planitt_signal.strategy,
                "reason": f"{planitt_signal.reason}{reason_suffix}",
                "validity": planitt_signal.validity,
                "created_at": created_at.isoformat(),
                "status": "OPEN",
                "risk_reward_ratio": planitt_signal.risk_reward_ratio,
                # Internal helpers for dedup/expiry on the backend.
                "expires_at": expires_at.isoformat() if expires_at else None,
                "dedup_key": dedup_key,
            }

            # Persist to Mongo directly so local/background generation always lands
            # in the canonical Planitt collection regardless of downstream backend behavior.
            await self._persist_signal_to_mongo(
                payload=payload,
                symbol=symbol,
                timeframe=timeframe,
                dedup_key=dedup_key,
            )
            await close_completed_signals(symbol, timeframe, features.price)

            # 6) Forward to backend (internal API key)
            await self._post_to_backend(payload, correlation_id=correlation_id)
            return payload
        except Exception:
            async with self._dedup_lock:
                self._dedup.pop(dedup_key, None)
            raise

    @staticmethod
    def _fallback_decision(features: Any):
        """
        Deterministic fallback when LLM is unavailable.
        Generates directional trades only on clear trend/momentum alignment.
        """
        ema20 = float(getattr(features, "ema20", 0.0) or 0.0)
        ema50 = float(getattr(features, "ema50", 0.0) or 0.0)
        ema200 = float(getattr(features, "ema200", 0.0) or 0.0)
        rsi = float(getattr(features, "rsi", 50.0) or 50.0)
        macd_hist = float(getattr(features, "macd_hist", 0.0) or 0.0)
        pre_conf = float(getattr(features, "pre_confidence", 0.0) or 0.0)
        setup_type = str(getattr(features, "setup_type", "confluence") or "confluence")

        bullish = ema20 >= ema50 >= ema200 and rsi >= 52 and macd_hist >= 0
        bearish = ema20 <= ema50 <= ema200 and rsi <= 48 and macd_hist <= 0
        if not bullish and not bearish:
            # Fallback to momentum direction when trend alignment is mixed.
            if abs(macd_hist) < 1e-6:
                return None
            bullish = macd_hist > 0
            bearish = macd_hist < 0

        signal_type = "BUY" if bullish else "SELL"
        min_conf = max(55, int(getattr(settings, "PLANITT_MIN_CONFIDENCE", 70)))
        confidence = max(min_conf, min(82, int(round(pre_conf * 100))))
        if setup_type in {"breakout_pullback", "breakout"}:
            confidence = min(88, confidence + 4)

        class _Decision:
            def __init__(self):
                self.signal_type = signal_type
                self.confidence = confidence
                self.strategy = f"deterministic_{setup_type}"
                self.reason = "Trend + momentum confluence fallback (LLM unavailable)"
                self.validity = "2-4 hours"
                self.risk_reward_ratio = "1:2.0"

        return _Decision()
        

    def _build_llm_input(self, features: Any, candle_list: Any) -> dict[str, Any]:
        # Keep input compact but sufficient for the model to justify decision.
        # Keep it smaller to reduce Ollama latency/timeouts during local scans.
        n = min(20, len(candle_list.candles))
        candles = candle_list.candles[-n:]
        return {
            "asset": features.asset,
            "timeframe": features.timeframe,
            "price": features.price,
            "ohlcv": {
                "open": [c.open for c in candles],
                "high": [c.high for c in candles],
                "low": [c.low for c in candles],
                "close": [c.close for c in candles],
                "volume": [c.volume for c in candles],
            },
            "indicators": {
                "RSI": round(features.rsi, 3),
                "MACD": {
                    "hist": round(features.macd_hist, 6),
                    "hist_prev": round(features.macd_hist_prev, 6),
                },
                "EMA": {"20": round(features.ema20, 6), "50": round(features.ema50, 6), "200": round(features.ema200, 6)},
                "ATR": round(features.atr, 6),
                "volume_ratio": round(features.volume_ratio, 3),
                "adx": features.adx,
            },
            "setup_candidates": {
                "setup_type": features.setup_type,
                "key_level": features.key_level,
                "confluence_hits": list(features.confluence_hits),
                "pre_confidence": round(features.pre_confidence, 3),
                "candlestick": {
                    "pattern": features.candlestick_pattern,
                    "bias": features.candlestick_bias,
                    "strength": round(features.candlestick_strength, 3),
                    "confirmed": features.candlestick_confirmed,
                },
            },
        }

    async def _post_to_backend(self, payload: dict[str, Any], *, correlation_id: str) -> None:
        base_url = settings.PLANITT_BACKEND_BASE_URL.rstrip("/")
        url = f"{base_url}/signals"
        api_key = settings.PLANITT_BACKEND_INTERNAL_API_KEY

        if not api_key or api_key == "change-me":
            logger.error(
                "Planitt backend API key missing; set PLANITT_BACKEND_INTERNAL_API_KEY",
                extra={"correlation_id": correlation_id, "asset": payload.get("asset")},
            )
            return

        headers = {"x-api-key": api_key, "x-correlation-id": correlation_id}
        max_retries = 4
        backoff = 0.8

        async with httpx.AsyncClient(timeout=15.0) as client:
            for attempt in range(1, max_retries + 1):
                try:
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code in (200, 201):
                        return
                    if resp.status_code == 409:
                        logger.info(
                            "Planitt backend deduped signal",
                            extra={"correlation_id": correlation_id, "asset": payload.get("asset")},
                        )
                        return
                    if resp.status_code >= 500:
                        logger.warning(
                            "Planitt backend error (retry)",
                            extra={
                                "correlation_id": correlation_id,
                                "asset": payload.get("asset"),
                                "status": resp.status_code,
                                "attempt": attempt,
                                "body": resp.text[:400],
                            },
                        )
                        raise RuntimeError(f"backend {resp.status_code}")

                    # Non-retryable failures (400/401 etc)
                    logger.error(
                        "Planitt backend rejected payload",
                        extra={"correlation_id": correlation_id, "asset": payload.get("asset"), "status": resp.status_code, "body": resp.text[:400]},
                    )
                    return
                except Exception as e:
                    if attempt >= max_retries:
                        logger.error(
                            "Planitt backend POST failed (max retries)",
                            extra={"correlation_id": correlation_id, "asset": payload.get("asset"), "error": str(e)},
                        )
                        return
                    sleep_s = backoff * (2 ** (attempt - 1)) + random.random() * 0.2
                    await asyncio.sleep(sleep_s)

    async def _persist_signal_to_mongo(
        self,
        *,
        payload: dict[str, Any],
        symbol: str,
        timeframe: str,
        dedup_key: str,
    ) -> None:
        verification = None
        if settings.SIGNAL_VERIFICATION_ENABLED:
            news_summary = None
            try:
                sentiment = await get_symbol_news_sentiment(symbol)
                news_summary = f"Recent weighted sentiment: {sentiment:.2f}"
            except Exception:
                news_summary = None
            result = await self.verifier.verify_signal(
                signal=payload,
                asset_class="CRYPTO",
                market_context={"timeframe": timeframe},
                news_summary=news_summary,
            )
            verification = result.to_dict()
        document = build_signal_document(
            payload=payload,
            symbol=symbol,
            timeframe=timeframe,
            dedup_key=dedup_key,
            verification=verification,
        )
        await persist_signal_document(document)

    @staticmethod
    def _normalize_confidence(value: float) -> float:
        v = float(value)
        if v > 1.0:
            v = v / 100.0
        return max(0.0, min(1.0, v))

    @staticmethod
    def _apply_news_adjustment(confidence: float, signal_type: str, news_sentiment: float) -> float:
        direction = 1.0 if signal_type == "BUY" else -1.0
        adjusted = confidence + (0.08 * news_sentiment * direction)
        return max(0.0, min(0.99, adjusted))

    async def _is_in_cooldown(self, *, symbol: str, timeframe: str) -> bool:
        db = await get_db()
        coll = db[crypto_signals_collection()]
        recent = await coll.find(
            crypto_signal_find_filter({"symbol": symbol, "timeframe": timeframe}),
            {"_id": 0, "timestamp": 1, "signal_type": 1},
        ).sort("timestamp", -1).limit(2).to_list(2)
        if not recent:
            return False
        latest = recent[0]
        ts = latest.get("timestamp")
        if not isinstance(ts, datetime):
            return False
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        elapsed = (now_utc() - ts).total_seconds()
        cooldown_candles = max(1, int(getattr(settings, "PLANITT_SIGNAL_COOLDOWN_CANDLES", 2)))
        return elapsed < timeframe_to_cycle_seconds(timeframe) * cooldown_candles

    async def _calibrated_confidence(self, features: Any, base_confidence: float, news_sentiment: float) -> float:
        # Lazy fit from existing outcomes if we have enough closed samples.
        if not self._calibration_fitted:
            await self._fit_calibration_model()
        if not self._calibration_fitted:
            return base_confidence
        x = [[
            float(getattr(features, "pre_confidence", 0.0)),
            float(getattr(features, "volume_ratio", 1.0)),
            float(getattr(features, "adx", 0.0) or 0.0),
            float(getattr(features, "rsi", 50.0)),
            float(news_sentiment),
            base_confidence,
        ]]
        try:
            probs = self._calibration_model.predict_proba(x)
            return float(probs[0][1])
        except Exception:
            return base_confidence

    async def _fit_calibration_model(self) -> None:
        db = await get_db()
        coll = db[crypto_signals_collection()]
        docs = await coll.find(
            crypto_signal_find_filter({"outcome": {"$in": ["tp_hit", "sl_hit"]}}),
            {"_id": 0, "confidence_score": 1, "pnl_r_multiple": 1, "risk_reward_ratio": 1, "signal_type": 1},
        ).limit(500).to_list(500)
        if len(docs) < 30:
            return
        x_rows: list[list[float]] = []
        y_rows: list[int] = []
        for doc in docs:
            conf = float(doc.get("confidence_score") or 0.0)
            rr = float(doc.get("risk_reward_ratio") or 0.0)
            pnl_r = float(doc.get("pnl_r_multiple") or 0.0)
            sig = str(doc.get("signal_type") or "HOLD")
            side = 1.0 if sig == "BUY" else -1.0 if sig == "SELL" else 0.0
            x_rows.append([conf, rr, pnl_r, side, 0.0, conf])
            y_rows.append(1 if doc.get("outcome") == "tp_hit" else 0)
        if len(set(y_rows)) < 2:
            return
        self._calibration_model.fit(x_rows, y_rows)
        self._calibration_fitted = True

