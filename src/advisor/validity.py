"""Trade validity windows in IST per SOP §5–6."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
TradeHorizon = Literal["intraday", "swing"]

# SOP: intraday + swing only — no scalping (1m/5m) or long-term (>7d) calls.
SOP_SCALPING_TIMEFRAMES = frozenset({"1m", "5m"})
SOP_INTRADAY_TIMEFRAMES = frozenset({"15m", "1h"})
SOP_SWING_TIMEFRAMES = frozenset({"4h", "1d"})
SOP_PUBLISH_TIMEFRAMES = SOP_INTRADAY_TIMEFRAMES | SOP_SWING_TIMEFRAMES

SOP_ENTRY_MISS_REVIEW_PCT = 1.0


def now_ist() -> datetime:
    return datetime.now(tz=IST)


def end_of_ist_day(dt: datetime) -> datetime:
    local = dt.astimezone(IST)
    return local.replace(hour=23, minute=59, second=59, microsecond=0)


def infer_trade_horizon(timeframe: str) -> TradeHorizon:
    if timeframe in SOP_INTRADAY_TIMEFRAMES:
        return "intraday"
    if timeframe in SOP_SWING_TIMEFRAMES:
        return "swing"
    if timeframe in ("5m", "1m"):
        return "intraday"
    return "swing"


def validate_publish_timeframe(timeframe: str) -> tuple[bool, str | None]:
    """Reject scalping and non-SOP timeframes before signal generation."""
    tf = timeframe.strip().lower()
    if tf in SOP_SCALPING_TIMEFRAMES:
        return False, f"scalping_timeframe_blocked_{tf}"
    if tf not in SOP_PUBLISH_TIMEFRAMES:
        return False, f"long_term_or_unsupported_timeframe_{tf}"
    return True, None


def infer_swing_days(timeframe: str, *, atr_pct: float | None = None) -> int:
    """
    Swing validity 2–7 calendar days (SOP §6), ending 23:59 IST on the final day.
    Higher volatility → shorter swing window; 1d charts get more runway.
    """
    base = {"4h": 3, "1d": 5}.get(timeframe, 3)
    if atr_pct is not None:
        if atr_pct > 4.0:
            base = max(2, base - 1)
        elif atr_pct < 1.5:
            base = min(7, base + 1)
    return max(2, min(7, base))


def compute_valid_until(
    trade_horizon: TradeHorizon,
    *,
    generated_at: datetime | None = None,
    swing_days: int = 3,
    timeframe: str = "1h",
) -> datetime:
    """
    SOP §6 — Intraday: valid until 23:59 IST the next calendar day.
    Swing: 2–7 days ending 23:59 IST on the final day.
    """
    start = (generated_at or now_ist()).astimezone(IST)
    if trade_horizon == "intraday":
        target_day = start.date() + timedelta(days=1)
    else:
        days = max(2, min(7, swing_days))
        target_day = start.date() + timedelta(days=days)
    return datetime(
        target_day.year,
        target_day.month,
        target_day.day,
        23,
        59,
        59,
        tzinfo=IST,
    )


def entry_band_miss_pct(
    live_price: float,
    entry_low: float,
    entry_high: float,
) -> float:
    """
    How far price missed the entry band (0 if inside).
    Used for SOP manual-close rule when miss is <1%.
    """
    low, high = sorted([entry_low, entry_high])
    mid = (low + high) / 2.0
    if mid <= 0:
        return 0.0
    if low <= live_price <= high:
        return 0.0
    if live_price < low:
        return (low - live_price) / mid * 100.0
    return (live_price - high) / mid * 100.0


def entry_miss_eligible_for_review(
    live_price: float,
    entry_low: float,
    entry_high: float,
    *,
    max_miss_pct: float = SOP_ENTRY_MISS_REVIEW_PCT,
) -> bool:
    miss = entry_band_miss_pct(live_price, entry_low, entry_high)
    return 0.0 < miss <= max_miss_pct
