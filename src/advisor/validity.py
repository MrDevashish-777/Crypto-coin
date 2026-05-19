"""Trade validity windows in IST per SOP §6."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
TradeHorizon = Literal["intraday", "swing"]


def now_ist() -> datetime:
    return datetime.now(tz=IST)


def end_of_ist_day(dt: datetime) -> datetime:
    local = dt.astimezone(IST)
    return local.replace(hour=23, minute=59, second=59, microsecond=0)


def compute_valid_until(
    trade_horizon: TradeHorizon,
    *,
    generated_at: datetime | None = None,
    swing_days: int = 3,
) -> datetime:
    """
    Intraday: valid until 23:59 IST next calendar day.
    Swing: valid swing_days (2-7 cap) ending 23:59 IST on final day.
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


def infer_trade_horizon(timeframe: str) -> TradeHorizon:
    if timeframe in ("15m", "1h", "5m", "1m"):
        return "intraday"
    return "swing"
