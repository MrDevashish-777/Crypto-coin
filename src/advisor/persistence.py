"""Persist advisor signals to MongoDB (optional audit)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

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


async def has_open_advisor_signal(symbol: str) -> bool:
    """Check if there is an existing OPEN advisor signal for a symbol."""
    db = await get_db()
    coll = db[crypto_signals_collection()]
    count = await coll.count_documents({
        "source_backend": "coindcx_advisor",
        "symbol": symbol.upper(),
        "status": "OPEN",
    })
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


async def close_advisor_signals(symbol: str, latest_price: float, candle_list: CandleList | None = None) -> int:
    """Close open advisor signals when TP/SL is hit."""
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
        direction = str(doc.get("direction", "BUY"))
        entry_range = doc.get("entry_range") or [0.0, 0.0]
        entry = (float(entry_range[0]) + float(entry_range[1])) / 2.0
        tp = float(doc.get("target") or 0.0)
        sl = float(doc.get("stop_loss") or 0.0)
        valid_until_str = doc.get("valid_until_ist")
        status = "OPEN"
        outcome = "open"
        
        is_expired = False
        if valid_until_str:
            try:
                valid_until = datetime.fromisoformat(valid_until_str.replace("Z", "+00:00"))
                if now > valid_until:
                    is_expired = True
            except Exception:
                pass

        generated_at_str = doc.get("generated_at")
        generated_ts = 0
        if generated_at_str:
            try:
                dt = datetime.fromisoformat(generated_at_str.replace("Z", "+00:00"))
                generated_ts = int(dt.timestamp() * 1000)
            except Exception:
                pass

        hit_tp = False
        hit_sl = False
        hit_price = latest_price

        # 1. Replay historical candles to catch hits during server downtime
        if candle_list is not None and generated_ts > 0:
            for candle in candle_list.candles:
                if candle.timestamp >= generated_ts:
                    if direction == "BUY":
                        if candle.high >= tp:
                            hit_tp = True
                            hit_price = tp
                            break
                        if candle.low <= sl:
                            hit_sl = True
                            hit_price = sl
                            break
                    else:
                        if candle.low <= tp:
                            hit_tp = True
                            hit_price = tp
                            break
                        if candle.high >= sl:
                            hit_sl = True
                            hit_price = sl
                            break

        # 2. If not hit in replay, check the live instantaneous price
        if not hit_tp and not hit_sl:
            if direction == "BUY":
                if latest_price >= tp:
                    hit_tp = True
                    hit_price = latest_price
                elif latest_price <= sl:
                    hit_sl = True
                    hit_price = latest_price
            elif direction == "SELL":
                if latest_price <= tp:
                    hit_tp = True
                    hit_price = latest_price
                elif latest_price >= sl:
                    hit_sl = True
                    hit_price = latest_price

        if hit_tp:
            status = "TP_HIT"
            outcome = "tp_hit"
        elif hit_sl:
            status = "SL_HIT"
            outcome = "sl_hit"

        if status == "OPEN" and is_expired:
            status = "EXPIRED"
            outcome = "expired"

        if status != "OPEN":
            risk = abs(entry - sl)
            reward_diff = (hit_price - entry) if direction == "BUY" else (entry - hit_price)
            pnl_r = (reward_diff / risk) if risk > 0 else None
            
            # Cap pnl_r at -1 for SL hits to normalize risk 
            if status == "SL_HIT" and pnl_r is not None and pnl_r < -1.0:
                pnl_r = -1.0

            await coll.update_one(
                {"signal_id": doc["signal_id"]},
                {
                    "$set": {
                        "status": status,
                        "outcome": outcome,
                        "closed_at": now.isoformat(),
                        "pnl_r_multiple": pnl_r,
                    }
                },
            )
            closed_count += 1
    return closed_count
