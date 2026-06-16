"""Persist advisor signals to MongoDB (optional audit)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from config.settings import settings
from src.advisor.reconciliation import doc_to_replay_params, replay_outcome_from_candles
from src.advisor.schemas import AdvisorSignal
from src.data.models import CandleList
from src.database.db import get_db
from src.planitt.mongo_collections import crypto_signals_collection

logger = logging.getLogger(__name__)


def build_advisor_document(signal: AdvisorSignal) -> dict[str, Any]:
    return {
        "signal_id": signal.signal_id,
        "asset_class": "CRYPTO",
        "source_backend": "coindcx_advisor",
        "symbol": signal.symbol,
        "pair": signal.pair,
        "margin_currency": signal.margin_currency,
        "direction": signal.direction,
        "trade_horizon": signal.trade_horizon,
        "timeframe": signal.timeframe,
        "entry_range": [signal.entry_low, signal.entry_high],
        "stop_loss": signal.stop_loss,
        "target": signal.target,
        "sl_pct": signal.sl_pct,
        "tp_pct": signal.tp_pct,
        "leverage": signal.leverage,
        "risk_reward": signal.risk_reward,
        "confidence_score": signal.confidence,
        "valid_until_ist": signal.valid_until_ist.isoformat(),
        "generated_at": signal.generated_at.isoformat(),
        "live_price_at_signal": signal.live_price_at_signal,
        "indicators": signal.indicators,
        "confluence_hits": signal.confluence_hits,
        "reason_why_token": signal.reason_why_token,
        "reason_entry": signal.reason_entry,
        "reason_monitor": signal.reason_monitor,
        "pdf_path": signal.pdf_path,
        "chart_path": signal.chart_path,
        "cloudinary_pdf_url": signal.cloudinary_pdf_url,
        "composite_score": signal.composite_score,
        "quality_tier": signal.quality_tier,
        "review_status": "AUTO_PUBLISHED",
        "status": "OPEN",
        "outcome": "open",
    }


async def persist_advisor_signal(signal: AdvisorSignal) -> str:
    db = await get_db()
    coll = db[crypto_signals_collection()]
    doc = build_advisor_document(signal)
    await coll.update_one(
        {"signal_id": signal.signal_id},
        {"$set": doc},
        upsert=True,
    )
    logger.info("Persisted advisor signal %s", signal.signal_id)
    return signal.signal_id


async def has_open_advisor_signal(symbol: str, timeframe: str | None = None) -> bool:
    """Check if there is an existing OPEN advisor signal for a symbol (and optional timeframe)."""
    db = await get_db()
    coll = db[crypto_signals_collection()]
    query: dict[str, Any] = {
        "source_backend": "coindcx_advisor",
        "symbol": symbol.upper(),
        "status": "OPEN",
    }
    if timeframe and settings.ADVISOR_ALLOW_MULTI_TF_PER_SYMBOL:
        query["timeframe"] = timeframe
    elif not settings.ADVISOR_ALLOW_MULTI_TF_PER_SYMBOL:
        pass  # any open on symbol blocks
    count = await coll.count_documents(query)
    return count > 0


async def load_weekly_publish_records() -> list[dict[str, str]]:
    """Load advisor publishes from last 7 days for allocation tracker."""
    db = await get_db()
    coll = db[crypto_signals_collection()]
    cutoff = datetime.now(timezone.utc).timestamp() - 7 * 86400
    cursor = coll.find(
        {"source_backend": "coindcx_advisor"},
        {"symbol": 1, "generated_at": 1},
    ).sort("generated_at", -1).limit(50)
    records: list[dict[str, str]] = []
    async for doc in cursor:
        gen = doc.get("generated_at")
        if isinstance(gen, str):
            try:
                ts = datetime.fromisoformat(gen.replace("Z", "+00:00"))
            except ValueError:
                continue
        elif isinstance(gen, datetime):
            ts = gen
        else:
            continue
        if ts.timestamp() < cutoff:
            continue
        records.append({"symbol": str(doc.get("symbol", "")).upper(), "at": ts.isoformat()})
    return records


async def _fetch_candles_for_signal(
    fetcher: Any,
    *,
    symbol: str,
    timeframe: str,
    generated_at: datetime,
    fallback: CandleList | None = None,
) -> CandleList | None:
    """Fetch OHLCV from signal generation time through now."""
    try:
        since = generated_at.astimezone(timezone.utc) - timedelta(hours=2)
        return await fetcher.fetch_candles_since(symbol, timeframe, since=since)
    except Exception as exc:
        logger.warning(
            "Historical fetch failed for %s %s, using fallback candles: %s",
            symbol,
            timeframe,
            exc,
        )
        return fallback


async def _close_single_document(
    doc: dict[str, Any],
    coll: Any,
    *,
    latest_price: float,
    candle_list: CandleList | None,
    fetcher: Any | None,
    now: datetime,
) -> bool:
    params = doc_to_replay_params(doc)
    candles = candle_list.candles if candle_list is not None else []

    if fetcher is not None and params["generated_ts_ms"] > 0:
        generated_at = datetime.fromtimestamp(
            params["generated_ts_ms"] / 1000, tz=timezone.utc
        )
        fetched = await _fetch_candles_for_signal(
            fetcher,
            symbol=params["symbol"],
            timeframe=params["timeframe"],
            generated_at=generated_at,
            fallback=candle_list,
        )
        if fetched is not None:
            candles = fetched.candles

    status, outcome, _hit_price, pnl_r = replay_outcome_from_candles(
        direction=params["direction"],
        entry=params["entry"],
        tp=params["tp"],
        sl=params["sl"],
        generated_ts_ms=params["generated_ts_ms"],
        valid_until=params["valid_until"],
        candles=candles,
        latest_price=latest_price,
        now=now,
    )

    if status == "OPEN":
        return False

    await coll.update_one(
        {"signal_id": doc["signal_id"]},
        {
            "$set": {
                "status": status,
                "outcome": outcome,
                "closed_at": now.isoformat(),
                "pnl_r_multiple": pnl_r if status in ("TP_HIT", "SL_HIT") else 0.0,
            }
        },
    )
    logger.info(
        "Closed signal %s %s -> %s (pnl_r=%.2f)",
        params["symbol"],
        doc.get("signal_id"),
        status,
        pnl_r,
    )
    return True


async def close_advisor_signals(
    symbol: str,
    latest_price: float,
    candle_list: CandleList | None = None,
    *,
    fetcher: Any | None = None,
) -> int:
    """Close open advisor signals for a symbol using per-signal timeframe replay."""
    db = await get_db()
    coll = db[crypto_signals_collection()]
    query = {
        "source_backend": "coindcx_advisor",
        "symbol": symbol.upper(),
        "status": "OPEN",
    }
    active_docs = await coll.find(query, {"_id": 0}).to_list(200)
    closed_count = 0
    now = datetime.now(timezone.utc)

    for doc in active_docs:
        tf = str(doc.get("timeframe") or "")
        per_tf_candles = candle_list if candle_list and candle_list.timeframe == tf else None
        if await _close_single_document(
            doc,
            coll,
            latest_price=latest_price,
            candle_list=per_tf_candles,
            fetcher=fetcher,
            now=now,
        ):
            closed_count += 1
    return closed_count


async def reconcile_all_open_signals(fetcher: Any | None = None) -> int:
    """
    Reconcile every OPEN advisor signal (startup + periodic).

    Fetches historical candles per signal timeframe from generated_at → now
    so TP/SL hits during downtime are not missed.
    """
    db = await get_db()
    coll = db[crypto_signals_collection()]
    docs = await coll.find(
        {"source_backend": "coindcx_advisor", "status": "OPEN"},
        {"_id": 0},
    ).to_list(500)

    if not docs:
        return 0

    own_fetcher = fetcher is None
    if own_fetcher:
        from src.data.data_fetcher import DataFetcher

        fetcher = DataFetcher()

    closed_count = 0
    now = datetime.now(timezone.utc)
    price_cache: dict[str, float] = {}

    try:
        for doc in docs:
            symbol = str(doc.get("symbol", "")).upper()
            if not symbol:
                continue
            if symbol not in price_cache:
                try:
                    price_cache[symbol] = await fetcher.get_current_price(symbol)
                except Exception as exc:
                    logger.warning("Price fetch failed for %s: %s", symbol, exc)
                    continue

            if await _close_single_document(
                doc,
                coll,
                latest_price=price_cache[symbol],
                candle_list=None,
                fetcher=fetcher,
                now=now,
            ):
                closed_count += 1
    finally:
        if own_fetcher and fetcher is not None:
            await fetcher.close()

    if closed_count:
        logger.info("Reconciled %d open advisor signals", closed_count)
    return closed_count
