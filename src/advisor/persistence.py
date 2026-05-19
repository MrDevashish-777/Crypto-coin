"""Persist advisor signals to MongoDB (optional audit)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.advisor.schemas import AdvisorSignal
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
        "review_status": "AUTO_PUBLISHED",
    }


async def persist_advisor_signal(signal: AdvisorSignal) -> str:
    db = await get_db()
    coll = crypto_signals_collection(db)
    doc = build_advisor_document(signal)
    await coll.update_one(
        {"signal_id": signal.signal_id},
        {"$set": doc},
        upsert=True,
    )
    logger.info("Persisted advisor signal %s", signal.signal_id)
    return signal.signal_id


async def load_weekly_publish_records() -> list[dict[str, str]]:
    """Load advisor publishes from last 7 days for allocation tracker."""
    db = await get_db()
    coll = crypto_signals_collection(db)
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
