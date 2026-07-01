from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, Optional

from config.settings import settings
from src.data.models import CandleList

logger = logging.getLogger(__name__)

SignalSide = Literal["BUY", "SELL"]
SetupType = Literal[
    "trend_pullback",
    "volume_breakout",
    "support_resistance_reversal",
    "fvg_ob_retest",
    "liquidity_sweep",
    "vwap_reclaim",
]

@dataclass(frozen=True)
class ConfluenceFeatures:
    asset: str
    timeframe: str
    side: SignalSide
    setup_type: SetupType

    price: float
    atr: float

    ema20: float
    ema50: float
    ema200: float

    rsi: float
    macd_hist: float
    macd_hist_prev: float

    volume: float
    volume_ratio: float

    key_level: float
    breakout_level: Optional[float]

    confluence_hits: tuple[str, ...]
    pre_confidence: float
    adx: Optional[float]
    candlestick_pattern: Optional[str]
    candlestick_bias: Optional[Literal["bull", "bear"]]
    candlestick_strength: float
    candlestick_confirmed: bool
    agreeing_sources: int
    mtf_score: float


@dataclass(frozen=True)
class ConfluenceEvaluation:
    features: Optional[ConfluenceFeatures]
    reject_reason: Optional[str]


def find_pivots(values: list[float], *, is_high: bool) -> list[tuple[int, float]]:
    """Exported for backwards compatibility."""
    from src.planitt.rules.trend import _find_pivots
    return _find_pivots(values, is_high=is_high)


def adx_trend_threshold_for_timeframe(timeframe: str) -> float:
    """Returns the ADX trend threshold for a specific timeframe."""
    if timeframe == "15m":
        return settings.PLANITT_15M_ADX_THRESHOLD
    if timeframe == "1h":
        return settings.PLANITT_1H_ADX_THRESHOLD
    if timeframe == "4h":
        return settings.PLANITT_4H_ADX_THRESHOLD
    if timeframe == "1d":
        return settings.PLANITT_1D_ADX_THRESHOLD
    return settings.PLANITT_ADX_TREND_THRESHOLD


def evaluate_confluence_pre_gates_with_reason(
    candle_list: CandleList,
    *,
    adx_trend_threshold: float = 25.0,
    volume_multiplier: float = 1.5,
    touch_tolerance_pct: float = 0.0025,
    min_confluence_hits: int = 3,
) -> ConfluenceEvaluation:
    from src.planitt.rules import (
        RuleContext,
        MarketRegimeRule,
        TrendAlignmentRule,
        MomentumRule,
        SetupsRule,
    )
    from src.planitt.pipeline import ConfluencePipeline

    required_len = settings.PLANITT_MIN_CANDLES
    if len(candle_list.closes) < required_len:
        return ConfluenceEvaluation(
            features=None, 
            reject_reason=f"insufficient_candles:{len(candle_list.closes)}/{required_len}"
        )

    context = RuleContext(
        candle_list=candle_list,
        adx_trend_threshold=adx_trend_threshold,
        volume_multiplier=volume_multiplier,
        touch_tolerance_pct=touch_tolerance_pct,
        min_confluence_hits=min_confluence_hits,
    )

    pipeline = ConfluencePipeline([
        MarketRegimeRule(),
        TrendAlignmentRule(),
        MomentumRule(),
        SetupsRule(),
    ])

    return pipeline.evaluate(context)


def evaluate_confluence_pre_gates(
    candle_list: CandleList,
    *,
    adx_trend_threshold: float = 25.0,
    volume_multiplier: float = 1.5,
    touch_tolerance_pct: float = 0.0025,
    min_confluence_hits: int = 3,
) -> Optional[ConfluenceFeatures]:
    result = evaluate_confluence_pre_gates_with_reason(
        candle_list,
        adx_trend_threshold=adx_trend_threshold,
        volume_multiplier=volume_multiplier,
        touch_tolerance_pct=touch_tolerance_pct,
        min_confluence_hits=min_confluence_hits,
    )
    return result.features
