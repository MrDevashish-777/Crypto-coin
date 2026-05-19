"""
Williams %R Indicator

A momentum oscillator that moves between 0 and -100.
Developed by Larry Williams.

Overbought: 0 to -20  (price near period high)
Oversold:  -80 to -100 (price near period low)

Complements RSI well: both identify reversals but Williams %R is faster.
"""

from __future__ import annotations


from typing import List, Optional, Dict
from src.indicators.base import BaseIndicator


class WilliamsR(BaseIndicator):
    """
    Williams %R momentum oscillator.

    Used for:
    - Identifying overbought/oversold conditions (faster than RSI)
    - Confirming RSI signals
    - Detecting momentum reversals
    """

    def __init__(self, period: int = 14, overbought: float = -20, oversold: float = -80):
        """
        Initialize Williams %R.

        Args:
            period: Lookback period (default 14)
            overbought: Overbought threshold (default -20)
            oversold: Oversold threshold (default -80)
        """
        super().__init__(period)
        self.overbought = overbought
        self.oversold = oversold
        self.r_values: List[Optional[float]] = []

    def calculate_from_ohlc(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
    ) -> List[Optional[float]]:
        """
        Calculate Williams %R.

        Formula: %R = (Highest High - Close) / (Highest High - Lowest Low) * -100

        Returns:
            List of Williams %R values (0 to -100)
        """
        n = len(closes)
        if n < self.period:
            return []

        self.r_values = [None] * (self.period - 1)

        for i in range(self.period - 1, n):
            period_highs = highs[i - self.period + 1 : i + 1]
            period_lows = lows[i - self.period + 1 : i + 1]

            highest_high = max(period_highs)
            lowest_low = min(period_lows)
            denom = highest_high - lowest_low

            if denom == 0:
                self.r_values.append(-50.0)  # mid-range when flat
            else:
                r = ((highest_high - closes[i]) / denom) * -100
                self.r_values.append(round(r, 4))

        self.values = [v for v in self.r_values if v is not None]
        return self.r_values

    def calculate(self, closes: List[float]) -> List[float]:
        raise NotImplementedError("Use calculate_from_ohlc() for Williams %R")

    def get_current_value(self) -> Optional[float]:
        """Get the latest %R value."""
        vals = [v for v in self.r_values if v is not None]
        return vals[-1] if vals else None

    def get_previous_value(self) -> Optional[float]:
        """Get the second-to-last %R value."""
        vals = [v for v in self.r_values if v is not None]
        return vals[-2] if len(vals) >= 2 else None

    def is_overbought(self) -> bool:
        """Current value is in overbought territory (>= -20)."""
        val = self.get_current_value()
        return val is not None and val >= self.overbought

    def is_oversold(self) -> bool:
        """Current value is in oversold territory (<= -80)."""
        val = self.get_current_value()
        return val is not None and val <= self.oversold

    def is_crossing_above_oversold(self) -> bool:
        """Crossing from oversold to normal = bullish signal."""
        curr = self.get_current_value()
        prev = self.get_previous_value()
        if curr is None or prev is None:
            return False
        return prev <= self.oversold and curr > self.oversold

    def is_crossing_below_overbought(self) -> bool:
        """Crossing from overbought to normal = bearish signal."""
        curr = self.get_current_value()
        prev = self.get_previous_value()
        if curr is None or prev is None:
            return False
        return prev >= self.overbought and curr < self.overbought

    def get_signal_score(self) -> Dict[str, float]:
        """
        Returns directional scores based on current %R value.
        Returns dict with 'bull_score' and 'bear_score' (0 to 1).
        """
        val = self.get_current_value()
        if val is None:
            return {"bull_score": 0.0, "bear_score": 0.0}

        # Normalize: -100 (oversold) -> 1.0 bull, 0 (overbought) -> 1.0 bear
        bull_score = (abs(val) - 80) / 20.0 if val <= self.oversold else 0.0
        bear_score = (val + 20) / 20.0 if val >= self.overbought else 0.0

        return {
            "bull_score": min(max(bull_score, 0.0), 1.0),
            "bear_score": min(max(bear_score, 0.0), 1.0),
        }
