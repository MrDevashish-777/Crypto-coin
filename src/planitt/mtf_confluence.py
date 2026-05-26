"""Multi-timeframe trend alignment for advisor signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from config.settings import settings
from src.data.models import CandleList
from src.indicators.ema import EMA
from src.indicators.ichimoku import Ichimoku
from src.indicators.supertrend import Supertrend
from src.signals.market_regime import MarketRegime, MarketRegimeDetector

SignalSide = Literal["BUY", "SELL"]

_HTF_MAP: dict[str, list[str]] = {
    "15m": ["1h", "4h"],
    "1h": ["4h", "1d"],
    "4h": ["1d"],
    "1d": [],
}


@dataclass(frozen=True)
class MTFAlignmentResult:
    aligned: bool
    mtf_score: float
    reject_reason: Optional[str]
    htf_details: tuple[str, ...]


def higher_timeframes_for(signal_tf: str) -> list[str]:
    return list(_HTF_MAP.get(signal_tf, []))


def _htf_side(closes: list[float], highs: list[float], lows: list[float], price: float) -> Optional[SignalSide]:
    ema20, ema50, ema200 = EMA(20), EMA(50), EMA(200)
    for ind in (ema20, ema50, ema200):
        ind.calculate(closes)
    e20, e50, e200 = ema20.latest_value, ema50.latest_value, ema200.latest_value

    st = Supertrend(atr_period=10, multiplier=3.0)
    st.calculate_from_ohlc(highs, lows, closes)
    st_trend = st.get_current().get("trend")

    if e20 is not None and e50 is not None and e200 is not None:
        if e20 > e50 > e200 and price > e50:
            return "BUY"
        if e20 < e50 < e200 and price < e50:
            return "SELL"

    if st_trend == 1 and price > (e50 or price):
        return "BUY"
    if st_trend == -1 and price < (e50 or price):
        return "SELL"

    ichi = Ichimoku()
    ichi.calculate_from_ohlc(highs, lows, closes)
    bull = ichi.bullish_signal_strength(price)
    bear = ichi.bearish_signal_strength(price)
    if bull > 0.55 and bull > bear:
        return "BUY"
    if bear > 0.55 and bear > bull:
        return "SELL"
    return None


def _ranging_htf_side(regime, signal_side: SignalSide) -> bool:
    """DI direction on a ranging HTF counts as soft alignment."""
    pd = regime.plus_di
    md = regime.minus_di
    if pd is None or md is None:
        return False
    if signal_side == "BUY":
        return pd > md
    return md > pd


def check_htf_alignment(
    signal_side: SignalSide,
    signal_tf: str,
    htf_candles: dict[str, CandleList],
) -> MTFAlignmentResult:
    """
    Verify higher-timeframe trend agrees with the signal side.
    Requires at least PLANITT_MTF_MIN_AGREEING HTFs (default 1 of N).
    """
    htfs = higher_timeframes_for(signal_tf)
    if not htfs:
        return MTFAlignmentResult(aligned=True, mtf_score=1.0, reject_reason=None, htf_details=())

    if not htf_candles:
        return MTFAlignmentResult(
            aligned=False,
            mtf_score=0.0,
            reject_reason="htf_data_missing",
            htf_details=(),
        )

    min_agree = max(1, settings.PLANITT_MTF_MIN_AGREEING)
    detector = MarketRegimeDetector()
    details: list[str] = []
    scores: list[float] = []
    misalign_reason: Optional[str] = None

    for tf in htfs:
        cl = htf_candles.get(tf)
        if cl is None or len(cl.closes) < 50:
            return MTFAlignmentResult(
                aligned=False,
                mtf_score=0.0,
                reject_reason=f"htf_insufficient_data:{tf}",
                htf_details=tuple(details),
            )

        regime = detector.detect(cl)
        price = cl.closes[-1]
        htf_side = _htf_side(cl.closes, cl.highs, cl.lows, price)

        if htf_side == signal_side:
            details.append(f"htf_ok_{tf}")
            scores.append(1.0)
            continue

        if regime.regime == MarketRegime.RANGING and settings.PLANITT_MTF_ALLOW_RANGING_HTF:
            if _ranging_htf_side(regime, signal_side):
                details.append(f"htf_ranging_di_{tf}")
                scores.append(0.75)
                continue
            misalign_reason = misalign_reason or f"htf_ranging:{tf}"
            continue

        if htf_side is None:
            misalign_reason = misalign_reason or f"htf_no_trend:{tf}"
            continue

        misalign_reason = f"htf_misalignment:{tf}:{htf_side}_vs_{signal_side}"

    if len(scores) >= min_agree:
        mtf_score = sum(scores) / max(len(scores), 1)
        return MTFAlignmentResult(
            aligned=True,
            mtf_score=mtf_score,
            reject_reason=None,
            htf_details=tuple(details),
        )

    return MTFAlignmentResult(
        aligned=False,
        mtf_score=sum(scores) / max(len(htfs), 1) if scores else 0.0,
        reject_reason=misalign_reason or "htf_insufficient_agreement",
        htf_details=tuple(details),
    )
