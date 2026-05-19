from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, Optional

from config.settings import settings
from src.data.models import CandleList
from src.indicators.ema import EMA
from src.indicators.rsi import RSI
from src.indicators.macd import MACD
from src.indicators.atr import ATR
from src.indicators.candlestick_patterns import detect_latest_candlestick_pattern
from src.signals.market_regime import MarketRegimeDetector, MarketRegime

logger = logging.getLogger(__name__)


SignalSide = Literal["BUY", "SELL"]
SetupType = Literal[
    "trend_pullback",
    "volume_breakout",
    "support_resistance_reversal",
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

    # Key levels used by TP/SL + entry-range formatting.
    key_level: float
    breakout_level: Optional[float]

    # Diagnostics / confluence evidence.
    confluence_hits: tuple[str, ...]
    pre_confidence: float  # 0..1
    adx: Optional[float]
    candlestick_pattern: Optional[str]
    candlestick_bias: Optional[Literal["bull", "bear"]]
    candlestick_strength: float
    candlestick_confirmed: bool


@dataclass(frozen=True)
class ConfluenceEvaluation:
    features: Optional[ConfluenceFeatures]
    reject_reason: Optional[str]


def _volume_ratio(volumes: list[float], lookback: int) -> float:
    if len(volumes) < lookback + 1:
        return 1.0
    prev = volumes[-(lookback + 1) : -1]
    avg = sum(prev) / max(len(prev), 1)
    if avg <= 0:
        return 1.0
    return volumes[-1] / avg


def _find_pivots(values: list[float], *, is_high: bool) -> list[tuple[int, float]]:
    """
    Simple local-extrema pivots.
    - pivot high: v[i] > v[i-1] and v[i] > v[i+1]
    - pivot low:  v[i] < v[i-1] and v[i] < v[i+1]
    """

    if len(values) < 3:
        return []

    pivots: list[tuple[int, float]] = []
    for i in range(1, len(values) - 1):
        prev_v = values[i - 1]
        curr_v = values[i]
        next_v = values[i + 1]
        if is_high and curr_v > prev_v and curr_v > next_v:
            pivots.append((i, curr_v))
        if not is_high and curr_v < prev_v and curr_v < next_v:
            pivots.append((i, curr_v))
    return pivots


def _choppiness_index(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    tr_values: list[float] = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        tr_values.append(tr)
    tr_sum = sum(tr_values[-period:])
    high_n = max(highs[-period:])
    low_n = min(lows[-period:])
    if high_n <= low_n:
        return 50.0
    import math
    return 100 * math.log10(tr_sum / (high_n - low_n)) / math.log10(period)


def _is_squeeze(closes: list[float], highs: list[float], lows: list[float], period: int = 20) -> bool:
    if len(closes) < period + 2:
        return False
    subset = closes[-period:]
    mean = sum(subset) / period
    variance = sum((x - mean) ** 2 for x in subset) / period
    std_dev = variance ** 0.5
    bb_upper = mean + (2 * std_dev)
    bb_lower = mean - (2 * std_dev)
    tr_values = []
    for i in range(len(closes) - period + 1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        tr_values.append(tr)
    atr = sum(tr_values) / max(1, len(tr_values))
    kc_upper = mean + (1.5 * atr)
    kc_lower = mean - (1.5 * atr)
    return bb_upper <= kc_upper and bb_lower >= kc_lower


def _swing_structure_ok(highs: list[float], lows: list[float], *, side: SignalSide) -> bool:
    """
    Validate HH/HL (up) or LH/LL (down) using last two pivots.
    """

    # Limit the analysis window to reduce noise and false pivots.
    window = min(80, len(highs))
    highs_w = highs[-window:]
    lows_w = lows[-window:]

    piv_highs = _find_pivots(highs_w, is_high=True)
    piv_lows = _find_pivots(lows_w, is_high=False)

    if len(piv_highs) < 2 or len(piv_lows) < 2:
        return False

    # Use the last 2 pivots of each type (already in chronological order).
    last2_highs = piv_highs[-2:]
    last2_lows = piv_lows[-2:]

    h1, h2 = last2_highs[0][1], last2_highs[1][1]
    l1, l2 = last2_lows[0][1], last2_lows[1][1]

    if side == "BUY":
        return h2 > h1 and l2 > l1
    # SELL
    return h2 < h1 and l2 < l1


def evaluate_confluence_pre_gates_with_reason(
    candle_list: CandleList,
    *,
    adx_trend_threshold: float = 25.0,
    volume_multiplier: float = 1.5,
    touch_tolerance_pct: float = 0.0025,  # 0.25%
    min_confluence_hits: int = 3,
) -> ConfluenceEvaluation:
    """
    Strict pre-gates:
    - EMA alignment (20/50/200)
    - HH/HL or LH/LL swing structure
    - Non-sideways filter using ADX/regime detection
    - Detect allowed setups + confluence evidence (2-3 hits minimum)
    """

    closes = candle_list.closes
    highs = candle_list.highs
    lows = candle_list.lows
    volumes = candle_list.volumes

    required_len = settings.PLANITT_MIN_CANDLES
    if len(closes) < required_len:
        return ConfluenceEvaluation(features=None, reject_reason=f"insufficient_candles:{len(closes)}/{required_len}")

    # --- Non-sideways filter (must be trending) ---
    regime_detector = MarketRegimeDetector()
    regime_result = regime_detector.detect(candle_list)
    if regime_result.regime == MarketRegime.RANGING:
        return ConfluenceEvaluation(features=None, reject_reason=f"regime_filtered:{regime_result.regime.value}")
    if regime_result.regime == MarketRegime.VOLATILE and not settings.PLANITT_ALLOW_VOLATILE_THROUGH_GATES:
        return ConfluenceEvaluation(features=None, reject_reason=f"regime_filtered:{regime_result.regime.value}")
    if regime_result.adx is None or regime_result.adx < adx_trend_threshold:
        return ConfluenceEvaluation(features=None, reject_reason=f"adx_below_threshold:{regime_result.adx}")

    # --- Trend alignment EMA stack (20/50/200) ---
    ema20_ind = EMA(period=20)
    ema50_ind = EMA(period=50)
    ema200_ind = EMA(period=200)
    ema20_ind.calculate(closes)
    ema50_ind.calculate(closes)
    ema200_ind.calculate(closes)

    ema20 = ema20_ind.latest_value
    ema50 = ema50_ind.latest_value
    ema200 = ema200_ind.latest_value
    if ema20 is None or ema50 is None or ema200 is None:
        return ConfluenceEvaluation(features=None, reject_reason="ema_unavailable")

    side: Optional[SignalSide] = None
    if ema20 > ema50 > ema200:
        side = "BUY"
    elif ema20 < ema50 < ema200:
        side = "SELL"
    elif settings.PLANITT_RELAX_SIDE_FROM_REGIME:
        # Pullbacks often break a perfect EMA stack while ADX/DI still show direction.
        adx_ok = regime_result.adx is not None and regime_result.adx >= adx_trend_threshold
        pd = regime_result.plus_di
        md = regime_result.minus_di
        di_bull = pd is not None and md is not None and pd > md
        di_bear = pd is not None and md is not None and md > pd
        if adx_ok and regime_result.regime == MarketRegime.TRENDING_UP and di_bull:
            side = "BUY"
        elif adx_ok and regime_result.regime == MarketRegime.TRENDING_DOWN and di_bear:
            side = "SELL"
        elif adx_ok and regime_result.regime == MarketRegime.VOLATILE and settings.PLANITT_ALLOW_VOLATILE_THROUGH_GATES:
            if di_bull:
                side = "BUY"
            elif di_bear:
                side = "SELL"
    if side is None:
        return ConfluenceEvaluation(features=None, reject_reason="ema_misalignment")

    # --- Swing structure HH/HL vs LH/LL ---
    swing_ok = _swing_structure_ok(highs, lows, side=side)
    if not swing_ok and settings.PLANITT_REQUIRE_SWING_STRUCTURE:
        return ConfluenceEvaluation(features=None, reject_reason="swing_structure_failed")

    # --- Indicators: RSI + MACD histogram direction ---
    rsi_ind = RSI(period=14)
    rsi_ind.calculate(closes)
    rsi = rsi_ind.latest_value
    prev_rsi = rsi_ind.previous_value
    if rsi is None or prev_rsi is None:
        return ConfluenceEvaluation(features=None, reject_reason="rsi_unavailable")

    macd_ind = MACD()
    macd_ind.calculate(closes)
    hist = macd_ind.histogram
    if len(hist) < 2:
        return ConfluenceEvaluation(features=None, reject_reason="macd_unavailable")
    macd_hist = hist[-1]
    macd_hist_prev = hist[-2]

    # --- Volatility + volume spike ---
    atr_ind = ATR(period=14)
    atr_values = atr_ind.calculate_from_ohlc(highs, lows, closes)
    if not atr_values:
        return ConfluenceEvaluation(features=None, reject_reason="atr_unavailable")
    atr = float(atr_values[-1])

    volume_ratio = _volume_ratio(volumes, lookback=20)
    current_volume = float(volumes[-1])
    price = float(closes[-1])

    # --- Allowed setups + confluence evidence ---
    confluence_hits: list[str] = []

    # 1) Trend alignment
    confluence_hits.append("ema_alignment")
    if swing_ok:
        confluence_hits.append("swing_structure")

    # 2) Indicator confirmation (RSI + MACD)
    if side == "BUY":
        # Keep momentum confirmation but allow broader RSI band in trends.
        indicator_ok = 30 <= rsi <= 70 and rsi >= prev_rsi and macd_hist > 0
    else:
        indicator_ok = 30 <= rsi <= 70 and rsi <= prev_rsi and macd_hist < 0
    if indicator_ok:
        confluence_hits.append("rsi_macd_confirmation")

    # 3) Volume spike
    if volume_ratio >= volume_multiplier:
        confluence_hits.append("volume_spike")
    choppiness = _choppiness_index(highs, lows, closes)
    if choppiness < 48:
        confluence_hits.append("low_choppiness")
    squeeze_on = _is_squeeze(closes, highs, lows)
    if squeeze_on:
        confluence_hits.append("squeeze_regime")

    # 4) Key level reaction (pullback touch OR breakout level break)
    lookback = 20
    prev_high = max(highs[-(lookback + 1) : -1]) if len(highs) > lookback + 1 else price
    prev_low = min(lows[-(lookback + 1) : -1]) if len(lows) > lookback + 1 else price

    pullback_touch = False
    breakout_break = False

    if side == "BUY":
        pullback_touch = abs(price - ema50) / ema50 <= touch_tolerance_pct
        breakout_break = price > prev_high
    else:
        pullback_touch = abs(price - ema50) / ema50 <= touch_tolerance_pct
        breakout_break = price < prev_low

    key_level: float
    breakout_level: Optional[float] = None

    setup_type: Optional[SetupType] = None
    if pullback_touch:
        confluence_hits.append("key_level_reaction_pullback")
        setup_type = "trend_pullback"
        key_level = ema50
    elif breakout_break:
        confluence_hits.append("key_level_reaction_breakout")
        setup_type = "volume_breakout"
        key_level = prev_high if side == "BUY" else prev_low
        breakout_level = key_level
    else:
        # Support/resistance reversal fallback: near most recent pivot high/low.
        # (Still strict: requires a meaningful pivot proximity and indicator confirmation.)
        piv_highs = _find_pivots(highs[-80:], is_high=True)
        piv_lows = _find_pivots(lows[-80:], is_high=False)
        if side == "BUY" and piv_lows:
            last_pivot_low = piv_lows[-1][1]
            near_level = abs(price - last_pivot_low) / last_pivot_low <= touch_tolerance_pct
            if near_level:
                confluence_hits.append("key_level_reaction_reversal")
                setup_type = "support_resistance_reversal"
                key_level = last_pivot_low
        elif side == "SELL" and piv_highs:
            last_pivot_high = piv_highs[-1][1]
            near_level = abs(price - last_pivot_high) / last_pivot_high <= touch_tolerance_pct
            if near_level:
                confluence_hits.append("key_level_reaction_reversal")
                setup_type = "support_resistance_reversal"
                key_level = last_pivot_high
        else:
            # Continuation fallback: allow momentum continuation setup when price holds trend side.
            if side == "BUY" and price > ema20 and macd_hist > 0:
                confluence_hits.append("trend_continuation")
                setup_type = "volume_breakout"
                key_level = ema20
            elif side == "SELL" and price < ema20 and macd_hist < 0:
                confluence_hits.append("trend_continuation")
                setup_type = "volume_breakout"
                key_level = ema20
            else:
                return ConfluenceEvaluation(features=None, reject_reason="no_valid_setup")

    if len(confluence_hits) < min_confluence_hits or setup_type is None:
        return ConfluenceEvaluation(features=None, reject_reason=f"confluence_hits_too_low:{len(confluence_hits)}")

    pattern_name: Optional[str] = None
    pattern_bias: Optional[Literal["bull", "bear"]] = None
    pattern_strength = 0.0
    pattern_confirmed = False
    if settings.ENABLE_CANDLESTICK_PATTERNS:
        pattern = detect_latest_candlestick_pattern(
            opens=candle_list.opens,
            highs=highs,
            lows=lows,
            closes=closes,
            volumes=volumes,
        )
        if pattern and pattern["strength"] >= settings.PATTERN_MIN_STRENGTH:
            pattern_name = pattern["pattern_name"]
            pattern_bias = pattern["bias"]
            pattern_strength = float(pattern["strength"])
            pattern_confirmed = bool(pattern["confirmation"])
            side_is_bull = side == "BUY"
            if (side_is_bull and pattern_bias == "bull") or ((not side_is_bull) and pattern_bias == "bear"):
                confluence_hits.append(f"candlestick_{pattern_name.lower()}")
                if pattern_confirmed:
                    confluence_hits.append("candlestick_confirmation")

    # Pre-confidence heuristic (0..1): more confluence hits and stronger volume ratio.
    pre_conf = min(0.95, 0.40 + (len(confluence_hits) * 0.10) + (max(0.0, volume_ratio - 1.0) * 0.06))
    if pattern_strength > 0 and pattern_confirmed:
        pre_conf = min(0.97, pre_conf + min(pattern_strength * 0.08, 0.06))

    return ConfluenceEvaluation(features=ConfluenceFeatures(
        asset=candle_list.symbol,
        timeframe=candle_list.timeframe,
        side=side,
        setup_type=setup_type,
        price=price,
        atr=atr,
        ema20=float(ema20),
        ema50=float(ema50),
        ema200=float(ema200),
        rsi=float(rsi),
        macd_hist=float(macd_hist),
        macd_hist_prev=float(macd_hist_prev),
        volume=current_volume,
        volume_ratio=float(volume_ratio),
        key_level=float(key_level),
        breakout_level=float(breakout_level) if breakout_level is not None else None,
        confluence_hits=tuple(confluence_hits),
        pre_confidence=float(pre_conf),
        adx=regime_result.adx,
        candlestick_pattern=pattern_name,
        candlestick_bias=pattern_bias,
        candlestick_strength=pattern_strength,
        candlestick_confirmed=pattern_confirmed,
    ), reject_reason=None)


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

