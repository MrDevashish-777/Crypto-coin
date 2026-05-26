"""Unified weighted indicator voting for production Planitt confluence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from config.settings import settings
from src.data.models import CandleList
from src.indicators.adx import ADX
from src.indicators.atr import ATR
from src.indicators.bollinger_bands import BollingerBands
from src.indicators.candlestick_patterns import detect_latest_candlestick_pattern
from src.indicators.cci import CCI
from src.indicators.ema import EMA
from src.indicators.fibonacci import FibonacciLevels
from src.indicators.heikin_ashi import HeikinAshi
from src.indicators.ichimoku import Ichimoku
from src.indicators.macd import MACD
from src.indicators.obv import OBV
from src.indicators.pivot_points import PivotPoints
from src.indicators.rsi import RSI
from src.indicators.smc import SMC
from src.indicators.stochastic import Stochastic
from src.indicators.supertrend import Supertrend
from src.indicators.vwap import VWAP
from src.indicators.nadaraya_watson import NadarayaWatsonEnvelope
from src.indicators.williams_r import WilliamsR

SignalSide = Literal["BUY", "SELL"]

INDICATOR_WEIGHTS: dict[str, float] = {
    "supertrend": 0.14,
    "ema_stack": 0.12,
    "ichimoku": 0.12,
    "nwe": settings.NWE_WEIGHT,
    "macd": 0.09,
    "rsi": 0.09,
    "volume_obv": 0.07,
    "vwap": 0.05,
    "bollinger": 0.05,
    "stochastic": 0.04,
    "cci": 0.04,
    "williams_r": 0.04,
    "heikin_ashi": 0.04,
    "fib_level": 0.04,
    "pivot_level": 0.04,
    "smc": 0.04,
    "candlestick": settings.PATTERN_WEIGHT,
}


@dataclass(frozen=True)
class IndicatorVoteResult:
    side: Optional[SignalSide]
    pre_confidence: float
    confluence_hits: tuple[str, ...]
    agreeing_sources: int
    bull_score: float
    bear_score: float
    reject_reason: Optional[str]


def _rsi_vote(closes: list[float]) -> tuple[Optional[str], float]:
    rsi = RSI(period=14)
    rsi.calculate(closes)
    if not rsi.is_ready():
        return None, 0.0
    val = rsi.latest_value
    prev = rsi.previous_value
    if val is None or prev is None:
        return None, 0.0
    if 40 <= val <= 65 and val >= prev:
        return "bull", max(0.0, (val - 40) / 25)
    if 35 <= val <= 60 and val <= prev:
        return "bear", max(0.0, (60 - val) / 25)
    return None, 0.0


def _macd_vote(closes: list[float]) -> tuple[Optional[str], float]:
    macd = MACD()
    macd.calculate(closes)
    hist = macd.histogram
    if len(hist) < 2:
        return None, 0.0
    if hist[-1] > 0 and hist[-1] > hist[-2]:
        return "bull", min(abs(hist[-1]) / (abs(hist[-1]) + 0.001), 0.9)
    if hist[-1] < 0 and hist[-1] < hist[-2]:
        return "bear", min(abs(hist[-1]) / (abs(hist[-1]) + 0.001), 0.9)
    return None, 0.0


def _ema_vote(closes: list[float]) -> tuple[Optional[str], float]:
    e9, e21, e50, e200 = EMA(9), EMA(21), EMA(50), EMA(200)
    for ind in (e9, e21, e50, e200):
        ind.calculate(closes)
    vals = [e9.latest_value, e21.latest_value, e50.latest_value, e200.latest_value]
    if any(v is None for v in vals):
        return None, 0.0
    bull = sum([vals[0] > vals[1], vals[1] > vals[2], vals[2] > vals[3]]) / 3.0
    bear = sum([vals[0] < vals[1], vals[1] < vals[2], vals[2] < vals[3]]) / 3.0
    if bull >= 0.67:
        return "bull", bull
    if bear >= 0.67:
        return "bear", bear
    return None, 0.0


def _supertrend_vote(highs, lows, closes) -> tuple[Optional[str], float]:
    st = Supertrend(atr_period=10, multiplier=3.0)
    st.calculate_from_ohlc(highs, lows, closes)
    c = st.get_current()
    if c["trend"] == 1:
        return "bull", 0.80
    if c["trend"] == -1:
        return "bear", 0.80
    return None, 0.0


def _ichimoku_vote(highs, lows, closes, price: float) -> tuple[Optional[str], float]:
    ichi = Ichimoku()
    ichi.calculate_from_ohlc(highs, lows, closes)
    bull = ichi.bullish_signal_strength(price)
    bear = ichi.bearish_signal_strength(price)
    if bull > 0.50 and bull > bear:
        return "bull", bull
    if bear > 0.50 and bear > bull:
        return "bear", bear
    return None, 0.0


def _obv_vote(closes, volumes) -> tuple[Optional[str], float]:
    obv = OBV()
    obv.calculate_from_cv(closes, volumes)
    if obv.is_rising(lookback=5):
        return "bull", 0.70
    if obv.is_falling(lookback=5):
        return "bear", 0.70
    return None, 0.0


def _vwap_vote(highs, lows, closes, volumes, price: float) -> tuple[Optional[str], float]:
    vwap = VWAP()
    vwap.calculate_from_ohlcv(highs, lows, closes, volumes)
    val = vwap.get_current().get("vwap")
    if val is None:
        return None, 0.0
    diff_pct = (price - val) / val
    if diff_pct > 0.002:
        return "bull", min(0.75, 0.5 + diff_pct * 10)
    if diff_pct < -0.002:
        return "bear", min(0.75, 0.5 + abs(diff_pct) * 10)
    return None, 0.0


def _bollinger_vote(closes, price: float) -> tuple[Optional[str], float]:
    bb = BollingerBands(period=20)
    bb.calculate(closes)
    bands = bb.get_bands()
    if not bands["upper"] or not bands["lower"]:
        return None, 0.0
    if bb.is_at_lower_band(price) and bb.is_expanding():
        return "bull", 0.65
    if bb.is_at_upper_band(price) and bb.is_expanding():
        return "bear", 0.65
    return None, 0.0


def _stochastic_vote(highs, lows, closes) -> tuple[Optional[str], float]:
    stoch = Stochastic(k_period=14, d_period=3)
    stoch.calculate_from_ohlc(highs, lows, closes)
    vals = stoch.get_values()
    k = vals.get("K")
    if k is None:
        return None, 0.0
    if stoch.is_oversold() and stoch.is_k_above_d():
        return "bull", min(0.80, max(0.4, (30 - k) / 30))
    if stoch.is_overbought() and not stoch.is_k_above_d():
        return "bear", min(0.80, max(0.4, (k - 70) / 30))
    if stoch.is_k_above_d():
        return "bull", 0.45
    return "bear", 0.45


def _cci_vote(highs, lows, closes) -> tuple[Optional[str], float]:
    cci = CCI(period=20)
    cci.calculate_from_ohlc(highs, lows, closes)
    scores = cci.get_signal_score()
    bs, brs = scores.get("bull_score", 0), scores.get("bear_score", 0)
    if bs > brs and bs > 0.3:
        return "bull", bs
    if brs > bs and brs > 0.3:
        return "bear", brs
    return None, 0.0


def _williams_vote(highs, lows, closes) -> tuple[Optional[str], float]:
    wr = WilliamsR(period=14)
    wr.calculate_from_ohlc(highs, lows, closes)
    scores = wr.get_signal_score()
    bs, brs = scores.get("bull_score", 0), scores.get("bear_score", 0)
    if bs > brs and bs > 0.3:
        return "bull", bs
    if brs > bs and brs > 0.3:
        return "bear", brs
    return None, 0.0


def _heikin_vote(opens, highs, lows, closes) -> tuple[Optional[str], float]:
    ha = HeikinAshi()
    candles = ha.calculate(opens, highs, lows, closes)
    if len(candles) < 3:
        return None, 0.0
    recent = candles[-3:]
    bull_count = sum(1 for c in recent if c.is_bullish)
    bear_count = sum(1 for c in recent if not c.is_bullish)
    if bull_count >= 2:
        return "bull", bull_count / 3.0
    if bear_count >= 2:
        return "bear", bear_count / 3.0
    return None, 0.0


def _fib_vote(highs, lows, closes, price: float) -> tuple[Optional[str], float]:
    fib = FibonacciLevels(swing_lookback=50)
    try:
        data = fib.calculate_from_ohlc(highs, lows, closes)
    except Exception:
        return None, 0.0
    retracements = data.get("retracements") or {}
    extensions = data.get("extensions") or {}
    tol = settings.PLANITT_TOUCH_TOLERANCE_PCT
    trend = data.get("trend", "up")
    for lvl in retracements.values():
        if lvl and abs(price - lvl) / lvl <= tol:
            if trend == "up":
                return "bull", 0.60
            return "bear", 0.60
    for lvl in extensions.values():
        if lvl and abs(price - lvl) / lvl <= tol:
            if trend == "up" and lvl > price:
                return "bull", 0.55
            if trend == "down" and lvl < price:
                return "bear", 0.55
    return None, 0.0


def _pivot_vote(highs, lows, closes, price: float) -> tuple[Optional[str], float]:
    if len(closes) < 2:
        return None, 0.0
    pivot = PivotPoints()
    try:
        levels = pivot.calculate_classic(
            prev_high=max(highs[-2:]),
            prev_low=min(lows[-2:]),
            prev_close=closes[-2],
        )
    except Exception:
        return None, 0.0
    tol = settings.PLANITT_TOUCH_TOLERANCE_PCT
    s1 = levels.get("s1")
    r1 = levels.get("r1")
    if s1 and abs(price - s1) / s1 <= tol:
        return "bull", 0.55
    if r1 and abs(price - r1) / r1 <= tol:
        return "bear", 0.55
    return None, 0.0


def _nwe_vote(closes: list[float], *, expected_side: SignalSide) -> tuple[Optional[str], float]:
    if not settings.ENABLE_NWE:
        return None, 0.0
    nwe = NadarayaWatsonEnvelope(
        bandwidth=settings.NWE_BANDWIDTH,
        multiplier=settings.NWE_MULTIPLIER,
        lookback=settings.NWE_LOOKBACK,
    )
    snap = nwe.snapshot(closes, band_touch_pct=settings.NWE_BAND_TOUCH_PCT)
    if snap is None:
        return None, 0.0
    strength = nwe.signal_strength(snap, expected_side)
    if strength < 0.45:
        return None, 0.0
    if expected_side == "BUY":
        return "bull", strength
    return "bear", strength


def _smc_vote(opens, highs, lows, closes, volumes, price: float) -> tuple[Optional[str], float]:
    smc = SMC()
    data = smc.calculate_from_ohlc(opens, highs, lows, closes, volumes)
    tol = settings.PLANITT_TOUCH_TOLERANCE_PCT
    for ob in reversed(data.get("order_blocks", [])[-5:]):
        if not ob.get("active"):
            continue
        mid = (ob["top"] + ob["bottom"]) / 2.0
        if abs(price - mid) / mid > tol:
            continue
        if ob["type"] == "bullish":
            return "bull", 0.65
        if ob["type"] == "bearish":
            return "bear", 0.65
    return None, 0.0


def _candlestick_vote(
    opens, highs, lows, closes, volumes,
    *,
    key_level: float,
    ema50: float,
) -> tuple[Optional[str], float, Optional[dict]]:
    if not settings.ENABLE_CANDLESTICK_PATTERNS:
        return None, 0.0, None
    pattern = detect_latest_candlestick_pattern(
        opens=opens, highs=highs, lows=lows, closes=closes, volumes=volumes,
    )
    if pattern is None or pattern["strength"] < settings.PATTERN_MIN_STRENGTH:
        return None, 0.0, pattern
    if settings.PATTERN_AT_LEVEL_REQUIRED:
        price = closes[-1]
        tol = settings.PLANITT_TOUCH_TOLERANCE_PCT
        at_level = any(
            lvl and abs(price - lvl) / lvl <= tol
            for lvl in (key_level, ema50)
        )
        if not at_level:
            return None, 0.0, pattern
    bias = pattern["bias"]
    return ("bull" if bias == "bull" else "bear"), float(pattern["strength"]), pattern


def evaluate_indicator_votes(
    candle_list: CandleList,
    *,
    expected_side: SignalSide,
    key_level: float,
    ema50: float,
) -> IndicatorVoteResult:
    """Compute weighted indicator votes; side must align with expected_side."""
    closes = candle_list.closes
    opens = candle_list.opens
    highs = candle_list.highs
    lows = candle_list.lows
    volumes = candle_list.volumes
    price = closes[-1]

    cs_dir, cs_score, _pattern = _candlestick_vote(
        opens, highs, lows, closes, volumes, key_level=key_level, ema50=ema50,
    )

    votes: dict[str, tuple[Optional[str], float]] = {
        "rsi": _rsi_vote(closes),
        "macd": _macd_vote(closes),
        "ema_stack": _ema_vote(closes),
        "supertrend": _supertrend_vote(highs, lows, closes),
        "ichimoku": _ichimoku_vote(highs, lows, closes, price),
        "volume_obv": _obv_vote(closes, volumes),
        "vwap": _vwap_vote(highs, lows, closes, volumes, price),
        "bollinger": _bollinger_vote(closes, price),
        "stochastic": _stochastic_vote(highs, lows, closes),
        "cci": _cci_vote(highs, lows, closes),
        "williams_r": _williams_vote(highs, lows, closes),
        "heikin_ashi": _heikin_vote(opens, highs, lows, closes),
        "fib_level": _fib_vote(highs, lows, closes, price),
        "pivot_level": _pivot_vote(highs, lows, closes, price),
        "smc": _smc_vote(opens, highs, lows, closes, volumes, price),
        "nwe": _nwe_vote(closes, expected_side=expected_side),
        "candlestick": (cs_dir, cs_score),
    }

    bull_score = 0.0
    bear_score = 0.0
    bull_sources = 0
    bear_sources = 0
    hits: list[str] = []

    for name, (direction, score) in votes.items():
        weight = INDICATOR_WEIGHTS.get(name, 0.05)
        if direction == "bull":
            bull_score += score * weight
            bull_sources += 1
            if expected_side == "BUY":
                hits.append(f"vote_{name}")
        elif direction == "bear":
            bear_score += score * weight
            bear_sources += 1
            if expected_side == "SELL":
                hits.append(f"vote_{name}")

    side_is_bull = expected_side == "BUY"
    win_score = bull_score if side_is_bull else bear_score
    lose_score = bear_score if side_is_bull else bull_score
    agreeing = bull_sources if side_is_bull else bear_sources
    total = win_score + lose_score + 1e-9
    agreement_ratio = win_score / total

    min_sources = settings.ADVISOR_MIN_AGREEING_SOURCES
    margin = settings.ADVISOR_MIN_VOTE_MARGIN

    if agreeing < min_sources:
        return IndicatorVoteResult(
            side=None,
            pre_confidence=0.0,
            confluence_hits=tuple(hits),
            agreeing_sources=agreeing,
            bull_score=bull_score,
            bear_score=bear_score,
            reject_reason=f"insufficient_votes:{agreeing}/{min_sources}",
        )

    if win_score <= lose_score or (win_score - lose_score) / total < margin:
        return IndicatorVoteResult(
            side=None,
            pre_confidence=0.0,
            confluence_hits=tuple(hits),
            agreeing_sources=agreeing,
            bull_score=bull_score,
            bear_score=bear_score,
            reject_reason=f"vote_margin_too_low:{win_score:.3f}_vs_{lose_score:.3f}",
        )

    pre_conf = min(
        0.97,
        0.35 + 0.45 * agreement_ratio + 0.20 * min(1.0, agreeing / min_sources),
    )

    return IndicatorVoteResult(
        side=expected_side,
        pre_confidence=pre_conf,
        confluence_hits=tuple(hits),
        agreeing_sources=agreeing,
        bull_score=bull_score,
        bear_score=bear_score,
        reject_reason=None,
    )
