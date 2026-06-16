"""Replay TP/SL/expiry for open advisor signals (e.g. after server downtime)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from src.data.models import Candle

logger = logging.getLogger(__name__)


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def replay_outcome_from_candles(
    *,
    direction: str,
    entry: float,
    tp: float,
    sl: float,
    generated_ts_ms: int,
    valid_until: Optional[datetime],
    candles: list[Candle],
    latest_price: float,
    now: Optional[datetime] = None,
) -> tuple[str, str, float, float]:
    """
    Determine signal status from candle replay + live price.

    Returns: (status, outcome, hit_price, pnl_r)
    """
    now = now or datetime.now(timezone.utc)
    hit_tp = False
    hit_sl = False
    hit_price = latest_price
    valid_until_ms = int(valid_until.timestamp() * 1000) if valid_until else None

    for candle in candles:
        if candle.timestamp < generated_ts_ms:
            continue
        if valid_until_ms is not None and candle.timestamp > valid_until_ms:
            break
        high, low = candle.high, candle.low
        if direction == "BUY":
            if low <= sl:
                hit_sl = True
                hit_price = sl
                break
            if high >= tp:
                hit_tp = True
                hit_price = tp
                break
        else:
            if high >= sl:
                hit_sl = True
                hit_price = sl
                break
            if low <= tp:
                hit_tp = True
                hit_price = tp
                break

    if not hit_tp and not hit_sl:
        if direction == "BUY":
            if latest_price >= tp:
                hit_tp = True
                hit_price = latest_price
            elif latest_price <= sl:
                hit_sl = True
                hit_price = latest_price
        else:
            if latest_price <= tp:
                hit_tp = True
                hit_price = latest_price
            elif latest_price >= sl:
                hit_sl = True
                hit_price = latest_price

    status = "OPEN"
    outcome = "open"
    if hit_tp:
        status, outcome = "TP_HIT", "tp_hit"
    elif hit_sl:
        status, outcome = "SL_HIT", "sl_hit"
    elif valid_until is not None and now > valid_until.astimezone(timezone.utc):
        status, outcome = "EXPIRED", "expired"
        hit_price = latest_price

    risk = abs(entry - sl)
    if status == "TP_HIT":
        reward_diff = (hit_price - entry) if direction == "BUY" else (entry - hit_price)
        pnl_r = (reward_diff / risk) if risk > 0 else 0.0
    elif status == "SL_HIT":
        reward_diff = (hit_price - entry) if direction == "BUY" else (entry - hit_price)
        pnl_r = (reward_diff / risk) if risk > 0 else -1.0
        if pnl_r < -1.0:
            pnl_r = -1.0
    else:
        pnl_r = 0.0

    return status, outcome, hit_price, pnl_r


def doc_to_replay_params(doc: dict[str, Any]) -> dict[str, Any]:
    direction = str(doc.get("direction", "BUY"))
    entry_range = doc.get("entry_range") or [0.0, 0.0]
    entry = (float(entry_range[0]) + float(entry_range[1])) / 2.0
    generated_at = _parse_dt(doc.get("generated_at"))
    generated_ts_ms = int(generated_at.timestamp() * 1000) if generated_at else 0
    valid_until = _parse_dt(doc.get("valid_until_ist"))
    return {
        "direction": direction,
        "entry": entry,
        "tp": float(doc.get("target") or 0.0),
        "sl": float(doc.get("stop_loss") or 0.0),
        "generated_ts_ms": generated_ts_ms,
        "valid_until": valid_until,
        "timeframe": str(doc.get("timeframe") or "1h"),
        "symbol": str(doc.get("symbol") or "").upper(),
    }
