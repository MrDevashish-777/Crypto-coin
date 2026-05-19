"""
CCI (Commodity Channel Index) Indicator

Measures the deviation of typical price from its moving average.
Originally developed for commodities, widely used for crypto.

CCI > +100: Overbought — potential sell or strong bull breakout
CCI < -100: Oversold — potential buy or strong bear breakdown
CCI crossing 0 upward = bullish momentum
CCI crossing 0 downward = bearish momentum
"""

from __future__ import annotations


from typing import List, Optional, Dict
from src.indicators.base import BaseIndicator


class CCI(BaseIndicator):
    """
    Commodity Channel Index for momentum and trend identification.

    Used for:
    - Detecting overbought/oversold conditions
    - Identifying new trends when crossing ±100
    - Momentum confirmation
    """

    def __init__(self, period: int = 20, constant: float = 0.015):
        """
        Initialize CCI.

        Args:
            period: Lookback period (default 20)
            constant: Lambert's constant (default 0.015)
        """
        super().__init__(period)
        self.constant = constant
        self.cci_values: List[Optional[float]] = []

    def calculate_from_ohlc(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
    ) -> List[Optional[float]]:
        """
        Calculate CCI values.

        Formula:
        Typical Price (TP) = (High + Low + Close) / 3
        CCI = (TP - SMA(TP, period)) / (constant * Mean Absolute Deviation)

        Returns:
            List of CCI values
        """
        n = len(closes)
        if n < self.period:
            return []

        typical_prices = [(highs[i] + lows[i] + closes[i]) / 3.0 for i in range(n)]

        self.cci_values = [None] * (self.period - 1)

        for i in range(self.period - 1, n):
            tp_window = typical_prices[i - self.period + 1 : i + 1]
            tp_mean = sum(tp_window) / self.period
            mad = sum(abs(tp - tp_mean) for tp in tp_window) / self.period

            if mad == 0:
                self.cci_values.append(0.0)
            else:
                cci = (typical_prices[i] - tp_mean) / (self.constant * mad)
                self.cci_values.append(round(cci, 4))

        self.values = [v for v in self.cci_values if v is not None]
        return self.cci_values

    def calculate(self, closes: List[float]) -> List[float]:
        raise NotImplementedError("Use calculate_from_ohlc() for CCI")

    def get_current_value(self) -> Optional[float]:
        vals = [v for v in self.cci_values if v is not None]
        return vals[-1] if vals else None

    def get_previous_value(self) -> Optional[float]:
        vals = [v for v in self.cci_values if v is not None]
        return vals[-2] if len(vals) >= 2 else None

    def is_overbought(self, level: float = 100) -> bool:
        val = self.get_current_value()
        return val is not None and val > level

    def is_oversold(self, level: float = -100) -> bool:
        val = self.get_current_value()
        return val is not None and val < level

    def is_strongly_overbought(self) -> bool:
        """CCI > +200 = extreme overbought."""
        val = self.get_current_value()
        return val is not None and val > 200

    def is_strongly_oversold(self) -> bool:
        """CCI < -200 = extreme oversold."""
        val = self.get_current_value()
        return val is not None and val < -200

    def crossed_above_zero(self) -> bool:
        """CCI crossed from negative to positive — bullish momentum."""
        curr = self.get_current_value()
        prev = self.get_previous_value()
        if curr is None or prev is None:
            return False
        return prev < 0 and curr >= 0

    def crossed_below_zero(self) -> bool:
        """CCI crossed from positive to negative — bearish momentum."""
        curr = self.get_current_value()
        prev = self.get_previous_value()
        if curr is None or prev is None:
            return False
        return prev > 0 and curr <= 0

    def crossed_above_100(self) -> bool:
        """CCI crossed above +100 — strong bullish breakout signal."""
        curr = self.get_current_value()
        prev = self.get_previous_value()
        if curr is None or prev is None:
            return False
        return prev <= 100 and curr > 100

    def crossed_below_minus100(self) -> bool:
        """CCI crossed below -100 — strong bearish breakdown signal."""
        curr = self.get_current_value()
        prev = self.get_previous_value()
        if curr is None or prev is None:
            return False
        return prev >= -100 and curr < -100

    def get_signal_score(self) -> Dict[str, float]:
        """Directional score based on CCI position."""
        val = self.get_current_value()
        if val is None:
            return {"bull_score": 0.0, "bear_score": 0.0}

        if val < -100:
            bull_score = min(abs(val + 100) / 100.0, 1.0)
            bear_score = 0.0
        elif val > 100:
            bear_score = min((val - 100) / 100.0, 1.0)
            bull_score = 0.0
        else:
            bull_score = 0.0
            bear_score = 0.0

        return {"bull_score": bull_score, "bear_score": bear_score}
