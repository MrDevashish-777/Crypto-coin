"""TP reachability gate — reject signals whose target is unlikely within SOP validity."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from config.constants import TIMEFRAME_SECONDS
from config.settings import settings
from src.advisor.validity import TradeHorizon, compute_valid_until, infer_trade_horizon

IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class ReachabilityResult:
    ok: bool
    reason: Optional[str]
    tp_distance_pct: float
    expected_move_pct: float
    trade_horizon: TradeHorizon
    hours_until_expiry: float


def _hours_until_expiry(
    trade_horizon: TradeHorizon,
    *,
    generated_at: datetime,
    timeframe: str,
    swing_days: int = 3,
) -> float:
    valid_until = compute_valid_until(
        trade_horizon,
        generated_at=generated_at,
        timeframe=timeframe,
        swing_days=swing_days,
    )
    start = generated_at.astimezone(IST)
    end = valid_until.astimezone(IST)
    return max(0.5, (end - start).total_seconds() / 3600.0)


def expected_move_pct(
    atr: float,
    price: float,
    *,
    timeframe: str,
    hours_until_expiry: float,
    k: float | None = None,
) -> float:
    """
    Estimate how far price may reasonably travel before expiry.

    Uses ATR% scaled by sqrt(time) relative to signal timeframe bar length.
    """
    multiplier = k if k is not None else settings.ADVISOR_REACHABILITY_K
    atr_pct = (atr / max(price, 1e-9)) * 100.0
    tf_seconds = TIMEFRAME_SECONDS.get(timeframe, 3600)
    tf_hours = max(tf_seconds / 3600.0, 0.25)
    time_scale = math.sqrt(max(hours_until_expiry, 0.5) / tf_hours)
    return multiplier * atr_pct * time_scale


def check_tp_reachability(
    *,
    entry_mid: float,
    target: float,
    atr: float,
    price: float,
    timeframe: str,
    trade_horizon: TradeHorizon,
    generated_at: datetime | None = None,
    swing_days: int = 3,
) -> ReachabilityResult:
    """Return whether TP distance is reachable within the given validity horizon."""
    if not settings.ADVISOR_REACHABILITY_GATE_ENABLED:
        tp_dist = abs(target - entry_mid) / max(entry_mid, 1e-9) * 100.0
        return ReachabilityResult(
            ok=True,
            reason=None,
            tp_distance_pct=tp_dist,
            expected_move_pct=tp_dist,
            trade_horizon=trade_horizon,
            hours_until_expiry=0.0,
        )

    at = (generated_at or datetime.now(tz=IST)).astimezone(IST)
    hours = _hours_until_expiry(
        trade_horizon,
        generated_at=at,
        timeframe=timeframe,
        swing_days=swing_days,
    )
    tp_distance_pct = abs(target - entry_mid) / max(entry_mid, 1e-9) * 100.0
    expected = expected_move_pct(
        atr,
        price,
        timeframe=timeframe,
        hours_until_expiry=hours,
    )
    ok = tp_distance_pct <= expected
    reason = None
    if not ok:
        reason = (
            f"tp_unreachable:tp={tp_distance_pct:.2f}%_expected={expected:.2f}%"
            f"_horizon={trade_horizon}"
        )
    return ReachabilityResult(
        ok=ok,
        reason=reason,
        tp_distance_pct=tp_distance_pct,
        expected_move_pct=expected,
        trade_horizon=trade_horizon,
        hours_until_expiry=hours,
    )


def resolve_reachability(
    *,
    entry_mid: float,
    target: float,
    atr: float,
    price: float,
    timeframe: str,
    generated_at: datetime | None = None,
) -> ReachabilityResult:
    """
    Check intraday reachability first; optionally upgrade to swing when enabled.
    """
    at = (generated_at or datetime.now(tz=IST)).astimezone(IST)
    default_horizon = infer_trade_horizon(timeframe)

    intraday = check_tp_reachability(
        entry_mid=entry_mid,
        target=target,
        atr=atr,
        price=price,
        timeframe=timeframe,
        trade_horizon="intraday",
        generated_at=at,
    )
    if intraday.ok:
        return intraday

    if default_horizon == "swing":
        swing = check_tp_reachability(
            entry_mid=entry_mid,
            target=target,
            atr=atr,
            price=price,
            timeframe=timeframe,
            trade_horizon="swing",
            generated_at=at,
        )
        return swing

    if settings.ADVISOR_REACHABILITY_AUTO_SWING:
        swing = check_tp_reachability(
            entry_mid=entry_mid,
            target=target,
            atr=atr,
            price=price,
            timeframe=timeframe,
            trade_horizon="swing",
            generated_at=at,
        )
        if swing.ok:
            return swing

    return intraday


def reachability_from_levels(
    levels: dict,
    *,
    atr: float,
    price: float,
    timeframe: str,
    generated_at: datetime | None = None,
) -> ReachabilityResult:
    """Convenience wrapper using computed advisor levels dict."""
    entry_mid = (float(levels["entry_low"]) + float(levels["entry_high"])) / 2.0
    return resolve_reachability(
        entry_mid=entry_mid,
        target=float(levels["target"]),
        atr=atr,
        price=price,
        timeframe=timeframe,
        generated_at=generated_at,
    )
