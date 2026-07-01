"""Adaptive scoring and level tuning — improve WR without hard-blocking signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from config.settings import settings
from src.advisor.live_performance import get_live_bucket_expectancy, load_live_bucket_expectancy, live_bucket_key
from src.data.models import CandleList

Direction = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class LevelAdjustments:
    sl_scale: float = 1.0
    tp_scale: float = 1.0
    vol_scale: float = 1.0
    regime: str = "trending"


def volatility_sl_scale(candle_list: Optional[CandleList], *, lookback: int = 50) -> float:
    """
    Widen stops when recent ATR is elevated vs longer history (reduces chop stop-outs).
    Returns 1.0–ADVISOR_VOL_SL_SCALE_MAX.
    """
    if candle_list is None or len(candle_list.closes) < lookback + 20:
        return 1.0
    from src.indicators.atr import ATR

    closes = candle_list.closes
    highs = candle_list.highs
    lows = candle_list.lows
    atr_ind = ATR(period=14)
    atr_ind.calculate_from_ohlc(highs, lows, closes)
    series = [v for v in atr_ind.values if v is not None]
    if len(series) < lookback:
        return 1.0
    recent = sum(series[-lookback:]) / lookback
    baseline = sum(series[-min(len(series), lookback * 4) :]) / max(
        len(series[-min(len(series), lookback * 4) :]), 1
    )
    if baseline <= 0:
        return 1.0
    ratio = recent / baseline
    cap = settings.ADVISOR_VOL_SL_SCALE_MAX
    if ratio <= 0.85:
        return 1.0
    if ratio >= 1.35:
        return cap
    return 1.0 + (cap - 1.0) * min(1.0, (ratio - 0.85) / 0.5)


def bucket_level_adjustments(
    symbol: str,
    timeframe: str,
    direction: Direction,
) -> tuple[float, float]:
    """
    Widen SL / trim TP on buckets with negative live expectancy (adapt, don't block).
    Returns (sl_scale, tp_scale).
    """
    if not settings.ADVISOR_ADAPTIVE_BUCKET_LEVELS:
        return 1.0, 1.0
    buckets = load_live_bucket_expectancy()
    key = live_bucket_key(symbol, timeframe, direction)
    entry = buckets.get(key) or buckets.get(live_bucket_key(symbol, timeframe))
    if not entry or int(entry.get("trades", 0)) < settings.ADVISOR_ADAPTIVE_BUCKET_MIN_TRADES:
        return 1.0, 1.0
    exp = float(entry.get("expectancy", 0))
    widen = settings.ADVISOR_BUCKET_SL_WIDEN_ON_NEGATIVE
    trim = settings.ADVISOR_BUCKET_TP_TRIM_ON_NEGATIVE
    if exp >= 0:
        boost = min(0.08, exp * 0.03)
        return max(1.0 - boost * 0.5, 0.92), min(1.0 + boost, 1.08)
    penalty = min(0.2, abs(exp) * 0.08)
    return 1.0 + widen * penalty / 0.12, max(0.85, 1.0 - trim * penalty / 0.12)


def regime_level_tuning(regime: str) -> tuple[float, float]:
    """Ranging/chop: wider SL, slightly closer TP for higher hit rate."""
    if regime == "ranging":
        return settings.ADVISOR_RANGING_SL_SCALE, settings.ADVISOR_RANGING_TP_SCALE
    if regime == "volatile":
        return settings.ADVISOR_VOLATILE_SL_SCALE, settings.ADVISOR_VOLATILE_TP_SCALE
    return 1.0, 1.0


def build_level_adjustments(
    *,
    candle_list: Optional[CandleList],
    symbol: str,
    timeframe: str,
    direction: Direction,
    regime: str,
) -> LevelAdjustments:
    vol = volatility_sl_scale(candle_list) if settings.ADVISOR_ADAPTIVE_VOL_STOPS else 1.0
    bucket_sl, bucket_tp = bucket_level_adjustments(symbol, timeframe, direction)
    reg_sl, reg_tp = regime_level_tuning(regime)
    return LevelAdjustments(
        sl_scale=vol * bucket_sl * reg_sl,
        tp_scale=bucket_tp * reg_tp,
        vol_scale=vol,
        regime=regime,
    )


def scale_stop_loss(
    entry_mid: float,
    stop_loss: float,
    *,
    side: Direction,
    sl_scale: float,
) -> float:
    if sl_scale <= 1.0 or entry_mid <= 0:
        return stop_loss
    dist = abs(entry_mid - stop_loss)
    new_dist = dist * sl_scale
    if side == "BUY":
        return entry_mid - new_dist
    return entry_mid + new_dist


def scale_target(
    entry_mid: float,
    target: float,
    *,
    side: Direction,
    tp_scale: float,
) -> float:
    if tp_scale == 1.0 or entry_mid <= 0:
        return target
    dist = abs(target - entry_mid)
    new_dist = dist * tp_scale
    if side == "BUY":
        return entry_mid + new_dist
    return entry_mid - new_dist


def adaptive_composite_adjustment(
    base_score: float,
    *,
    side: Direction,
    macro_alignment: float,
    symbol: str = "",
    timeframe: str = "",
) -> float:
    """Soft macro + bucket bias on ranking score (no hard reject)."""
    score = base_score
    if settings.ADVISOR_ADAPTIVE_MACRO_SCORING:
        w = settings.ADVISOR_MACRO_ALIGNMENT_WEIGHT
        if side == "BUY":
            score += w * macro_alignment
        else:
            score -= w * macro_alignment
    if symbol and timeframe and settings.ADVISOR_ADAPTIVE_BUCKET_RANKING:
        exp = get_live_bucket_expectancy(symbol, timeframe, direction=side)
        if exp is None:
            exp = get_live_bucket_expectancy(symbol, timeframe)
        if exp is not None:
            if exp > 0:
                score += min(0.1, exp * 0.035)
            elif exp < 0:
                score -= min(0.12, abs(exp) * 0.05)
    return score
