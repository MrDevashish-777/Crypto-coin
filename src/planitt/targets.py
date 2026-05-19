from __future__ import annotations

import logging
from typing import Literal

from config.settings import settings
from src.planitt.confluence import ConfluenceFeatures
from src.risk.risk_manager import RiskManager

logger = logging.getLogger(__name__)


def _entry_range_pullback(ema50: float, *, atr: float) -> list[float]:
    # Pullback entry zone around EMA50; ATR provides scale.
    half = max(ema50 * 0.0025, atr * 0.04)
    return [ema50 - half, ema50 + half]


def _entry_range_breakout(key_level: float, direction: Literal["long", "short"], *, atr: float) -> list[float]:
    # Breakout retest band around the breakout level.
    # Using small ATR scale to keep it realistic across assets.
    width = max(key_level * 0.0015, atr * 0.03)
    if direction == "long":
        return [key_level + width * 0.25, key_level + width * 1.25]
    return [key_level - width * 1.25, key_level - width * 0.25]


def _entry_range_reversal(key_level: float, direction: Literal["long", "short"], *, atr: float) -> list[float]:
    # Reversal entry near support/resistance with ATR-aware buffer.
    half = max(key_level * 0.0018, atr * 0.035)
    if direction == "long":
        return [key_level + half * 0.15, key_level + half * 1.15]
    return [key_level - half * 1.15, key_level - half * 0.15]


def compute_planitt_targets(features: ConfluenceFeatures) -> dict:
    """
    Compute Planitt numeric execution levels (entry_range, stop_loss, tp1/tp2/tp3).

    Uses deterministic ATR-based RR enforcement from RiskManager.
    """

    side = features.side
    direction = "long" if side == "BUY" else "short"
    safe_atr = max(float(features.atr or 0.0), max(float(features.price) * 0.0008, 1e-6))

    rm = RiskManager(
        min_risk_reward=settings.MIN_RISK_REWARD_RATIO,
        max_position_percent=settings.MAX_POSITION_SIZE,
        min_position_percent=settings.MIN_POSITION_SIZE,
    )

    entry_center: float
    if features.setup_type == "trend_pullback":
        entry_range = _entry_range_pullback(features.ema50, atr=safe_atr)
        entry_center = sum(entry_range) / 2.0
    elif features.setup_type == "volume_breakout":
        entry_range = _entry_range_breakout(features.key_level, direction, atr=safe_atr)
        entry_center = sum(entry_range) / 2.0
    else:
        entry_range = _entry_range_reversal(features.key_level, direction, atr=safe_atr)
        entry_center = sum(entry_range) / 2.0

    strong_tp3 = (
        features.pre_confidence >= 0.75
        and features.volume_ratio >= 2.0
        and len(features.confluence_hits) >= 4
    )

    tp1, tp2, tp3, sl, meta = rm.calculate_multi_tp_sl(
        entry_price=entry_center,
        atr=safe_atr,
        direction=direction,
        regime="trending",
        strong_trend_for_tp3=strong_tp3,
    )

    pattern_risk_adjusted = False
    if (
        settings.PATTERN_RISK_ADJUSTMENT_ENABLED
        and features.candlestick_pattern
        and features.candlestick_confirmed
        and features.candlestick_strength >= settings.PATTERN_MIN_STRENGTH
    ):
        pattern_risk_adjusted = True
        if direction == "long":
            sl = sl + (entry_center - sl) * 0.08
        else:
            sl = sl - (sl - entry_center) * 0.08

    # Strict ordering adjustments relative to the computed entry_range.
    entry_low, entry_high = sorted(entry_range)

    if side == "BUY":
        if sl >= entry_low:
            sl = entry_low - max(safe_atr * 0.08, entry_low * 0.0005)
        min_tp = entry_high + max(safe_atr * 0.08, entry_high * 0.0005)
        if not (tp1 > entry_high and tp2 > entry_high and tp3 > entry_high and tp1 < tp2 < tp3):
            tp1 = min_tp
            tp2 = min_tp + max(safe_atr * 0.12, min_tp * 0.001)
            tp3 = tp2 + max(safe_atr * 0.18, min_tp * 0.0015)
    else:
        if sl <= entry_high:
            sl = entry_high + max(safe_atr * 0.08, entry_high * 0.0005)
        max_tp = entry_low - max(safe_atr * 0.08, entry_low * 0.0005)
        if not (tp3 < tp2 < tp1 and tp1 < entry_low and tp2 < entry_low and tp3 < entry_low):
            tp1 = max_tp
            tp2 = max_tp - max(safe_atr * 0.12, abs(max_tp) * 0.001)
            tp3 = tp2 - max(safe_atr * 0.18, abs(max_tp) * 0.0015)

    entry_mid = (entry_low + entry_high) / 2.0
    risk = abs(entry_mid - sl)
    reward_tp2 = abs(tp2 - entry_mid)
    rr_tp2 = reward_tp2 / max(risk, 1e-9)
    risk_reward_ratio = f"1:{rr_tp2:.1f}"

    return {
        "entry_range": [round(entry_low, 6), round(entry_high, 6)],
        "stop_loss": round(float(sl), 6),
        "take_profit": {
            "tp1": round(float(tp1), 6),
            "tp2": round(float(tp2), 6),
            "tp3": round(float(tp3), 6),
        },
        "risk_reward_ratio": risk_reward_ratio,
        "numeric_meta": meta,
        "strong_tp3": strong_tp3,
        "pattern_risk_adjusted": pattern_risk_adjusted,
    }

