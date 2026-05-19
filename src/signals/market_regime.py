"""
Market Regime Detector

Classifies the current market into one of four regimes:
- TRENDING_UP:   Strong upward trend (ADX > 25, +DI > -DI, price above EMAs)
- TRENDING_DOWN: Strong downward trend (ADX > 25, -DI > +DI, price below EMAs)
- RANGING:       Sideways / low-momentum market (ADX < 20, BB tight)
- VOLATILE:      High volatility with no clear trend (ATR spike, BB expanding)

The regime is used by strategies to:
1. Select appropriate ATR multipliers for TP/SL
2. Enable/disable certain strategies (e.g. RSI mean-reversion only in RANGING)
3. Adjust signal confidence scores
"""

from __future__ import annotations


import logging
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum

from src.indicators.adx import ADX
from src.indicators.atr import ATR
from src.indicators.bollinger_bands import BollingerBands
from src.indicators.ema import EMA
from src.data.models import CandleList

logger = logging.getLogger(__name__)


class MarketRegime(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


@dataclass
class RegimeResult:
    regime: MarketRegime
    adx: Optional[float]
    plus_di: Optional[float]
    minus_di: Optional[float]
    atr: Optional[float]
    atr_pct_of_price: Optional[float]  # ATR as % of price
    bb_bandwidth: Optional[float]      # Bollinger Band bandwidth
    price_vs_ema50: Optional[str]      # 'above' or 'below'
    confidence: float                  # 0.0 - 1.0


class MarketRegimeDetector:
    """
    Classifies the market regime using ADX, ATR, Bollinger Bands, and EMAs.

    Usage:
        detector = MarketRegimeDetector()
        result = detector.detect(candle_list)
        print(result.regime)  # MarketRegime.TRENDING_UP
    """

    def __init__(
        self,
        adx_period: int = 14,
        atr_period: int = 14,
        bb_period: int = 20,
        ema_fast: int = 21,
        ema_slow: int = 50,
        adx_trend_threshold: float = 25.0,
        adx_ranging_threshold: float = 20.0,
        volatile_atr_multiplier: float = 1.5,  # ATR > 1.5x average = volatile
    ):
        self.adx_ind = ADX(period=adx_period)
        self.atr_ind = ATR(period=atr_period)
        self.bb_ind = BollingerBands(period=bb_period)
        self.ema_fast_ind = EMA(period=ema_fast)
        self.ema_slow_ind = EMA(period=ema_slow)

        self.adx_trend_threshold = adx_trend_threshold
        self.adx_ranging_threshold = adx_ranging_threshold
        self.volatile_atr_multiplier = volatile_atr_multiplier

    def detect(self, candle_list: CandleList) -> RegimeResult:
        """
        Detect the current market regime.

        Args:
            candle_list: CandleList with at least 60 candles

        Returns:
            RegimeResult with regime classification and indicator values
        """
        closes = candle_list.closes
        highs = candle_list.highs
        lows = candle_list.lows
        n = len(closes)

        if n < 52:  # Need enough for all indicators
            return RegimeResult(
                regime=MarketRegime.UNKNOWN,
                adx=None, plus_di=None, minus_di=None,
                atr=None, atr_pct_of_price=None,
                bb_bandwidth=None, price_vs_ema50=None, confidence=0.0
            )

        # Calculate all indicators
        adx_result = self.adx_ind.calculate_from_ohlc(highs, lows, closes)
        adx_current = self.adx_ind.get_current()

        atr_values = self.atr_ind.calculate_from_ohlc(highs, lows, closes)
        current_atr = atr_values[-1] if atr_values else None
        avg_atr = sum(atr_values[-20:]) / min(20, len(atr_values)) if atr_values else None

        self.bb_ind.calculate(closes)
        bb_data = self.bb_ind.get_bands()
        bb_bandwidth = bb_data.get("bandwidth")
        bb_widths = self.bb_ind.bandwidth

        self.ema_fast_ind.calculate(closes)
        self.ema_slow_ind.calculate(closes)
        ema_slow_val = self.ema_slow_ind.latest_value
        current_price = closes[-1]

        # --- Classification Logic ---
        adx_val = adx_current.get("adx")
        plus_di = adx_current.get("plus_di")
        minus_di = adx_current.get("minus_di")

        price_vs_ema50 = None
        if ema_slow_val is not None:
            price_vs_ema50 = "above" if current_price > ema_slow_val else "below"

        # Check for VOLATILE: ATR is significantly above recent average
        is_volatile = False
        if current_atr and avg_atr and avg_atr > 0:
            atr_ratio = current_atr / avg_atr
            is_volatile = atr_ratio > self.volatile_atr_multiplier
            # Also volatile if BB bandwidth is rapidly expanding
            if len(bb_widths) >= 5:
                bw_ratio = bb_widths[-1] / (sum(bb_widths[-5:-1]) / 4) if sum(bb_widths[-5:-1]) > 0 else 1
                if bw_ratio > 1.5:
                    is_volatile = True

        # Check for RANGING: ADX below threshold
        is_ranging = adx_val is not None and adx_val < self.adx_ranging_threshold

        # Check for TRENDING: ADX above threshold + DI alignment
        is_trending = adx_val is not None and adx_val >= self.adx_trend_threshold

        # Final classification with confidence
        regime = MarketRegime.UNKNOWN
        confidence = 0.5

        if is_volatile:
            regime = MarketRegime.VOLATILE
            confidence = min(0.9, (current_atr / avg_atr - 1.0) * 0.7 + 0.5) if avg_atr else 0.6

        elif is_ranging:
            regime = MarketRegime.RANGING
            # Higher confidence the lower ADX is
            confidence = min(0.90, 0.50 + (self.adx_ranging_threshold - adx_val) / self.adx_ranging_threshold * 0.4)

        elif is_trending:
            # Direction from DI lines
            if plus_di is not None and minus_di is not None and plus_di > minus_di:
                regime = MarketRegime.TRENDING_UP
                # Extra confirmation from price above slow EMA
                if price_vs_ema50 == "above":
                    confidence = min(0.95, 0.65 + (adx_val - 25) / 40)
                else:
                    confidence = 0.60
            else:
                regime = MarketRegime.TRENDING_DOWN
                if price_vs_ema50 == "below":
                    confidence = min(0.95, 0.65 + (adx_val - 25) / 40)
                else:
                    confidence = 0.60
        else:
            # Borderline — weak trend
            if adx_val and adx_val >= 20:
                regime = MarketRegime.TRENDING_UP if (plus_di or 0) > (minus_di or 0) else MarketRegime.TRENDING_DOWN
            else:
                regime = MarketRegime.RANGING
            confidence = 0.50

        adx_str = f"{adx_val:.1f}" if adx_val is not None else "N/A"
        atr_str = f"{current_atr:.4f}" if current_atr is not None else "N/A"
        logger.info(
            f"Market Regime: {regime.value} | ADX={adx_str} "
            f"| ATR={atr_str} | Confidence={confidence:.2f}"
        )

        return RegimeResult(
            regime=regime,
            adx=round(adx_val, 2) if adx_val else None,
            plus_di=round(plus_di, 2) if plus_di else None,
            minus_di=round(minus_di, 2) if minus_di else None,
            atr=round(current_atr, 6) if current_atr else None,
            atr_pct_of_price=round(current_atr / current_price * 100, 3) if current_atr else None,
            bb_bandwidth=round(bb_bandwidth, 6) if bb_bandwidth else None,
            price_vs_ema50=price_vs_ema50,
            confidence=round(confidence, 3),
        )

    def get_strategy_preference(self, regime: MarketRegime) -> List[str]:
        """
        Return ordered list of preferred strategy names for a given regime.
        Strategies listed first should be weighted higher.
        """
        preferences = {
            MarketRegime.TRENDING_UP: [
                "supertrend", "ema_trend", "ichimoku", "macd", "volume_breakout", "confluence"
            ],
            MarketRegime.TRENDING_DOWN: [
                "supertrend", "ema_trend", "ichimoku", "macd", "volume_breakout", "confluence"
            ],
            MarketRegime.RANGING: [
                "rsi", "bollinger_squeeze", "stochastic_rsi", "confluence"
            ],
            MarketRegime.VOLATILE: [
                "bollinger_squeeze", "rsi", "confluence"
            ],
            MarketRegime.UNKNOWN: ["rsi", "macd"],
        }
        return preferences.get(regime, ["rsi", "macd"])
