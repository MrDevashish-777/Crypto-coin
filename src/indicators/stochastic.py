"""
Stochastic Oscillator Indicator
"""

from typing import List, Dict, Optional
from src.indicators.base import BaseIndicator


class Stochastic(BaseIndicator):
    """
    Stochastic Oscillator
    
    Standard settings:
    - K period: 14
    - D period: 3
    - Overbought: 80
    - Oversold: 20
    """

    def __init__(
        self,
        k_period: int = 14,
        d_period: int = 3,
        overbought: float = 80,
        oversold: float = 20,
    ):
        """Initialize Stochastic"""
        super().__init__(k_period)
        self.d_period = d_period
        self.overbought = overbought
        self.oversold = oversold
        self.k_line: List[Optional[float]] = []
        self.d_line: List[Optional[float]] = []

    def calculate_from_ohlc(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
    ) -> tuple:
        """
        Calculate Stochastic Oscillator
        
        Args:
            highs: List of high prices
            lows: List of low prices
            closes: List of close prices
        
        Returns:
            Tuple of (k_line, d_line)
        """
        if len(closes) < self.period:
            return [], []

        self.k_line = []
        self.d_line = []

        # Calculate K line
        for i in range(self.period - 1, len(closes)):
            period_highs = highs[i - self.period + 1 : i + 1]
            period_lows = lows[i - self.period + 1 : i + 1]

            lowest_low = min(period_lows)
            highest_high = max(period_highs)

            if highest_high - lowest_low == 0:
                k_value = 50.0
            else:
                k_value = 100 * (closes[i] - lowest_low) / (highest_high - lowest_low)

            self.k_line.append(k_value)

        # Calculate D line (SMA of K)
        if len(self.k_line) >= self.d_period:
            for i in range(len(self.k_line) - self.d_period + 1):
                d_value = sum(self.k_line[i : i + self.d_period]) / self.d_period
                self.d_line.append(d_value)

        # Pad early values
        self.k_line = [None] * (self.period - 1) + self.k_line
        self.d_line = [None] * (self.period + self.d_period - 2) + self.d_line

        self.values = [x for x in self.k_line if x is not None]
        return self.k_line, self.d_line

    def calculate(self, closes: List[float]) -> List[float]:
        """Stochastic requires OHLC data"""
        raise NotImplementedError("Use calculate_from_ohlc() instead")

    def get_values(self) -> Dict[str, Optional[float]]:
        """Get current K and D values"""
        return {
            "K": self.k_line[-1] if self.k_line else None,
            "D": self.d_line[-1] if self.d_line else None,
        }

    def is_overbought(self) -> bool:
        """Check if Stochastic is overbought"""
        return self.k_line[-1] is not None and self.k_line[-1] > self.overbought

    def is_oversold(self) -> bool:
        """Check if Stochastic is oversold"""
        return self.k_line[-1] is not None and self.k_line[-1] < self.oversold

    def is_k_above_d(self) -> bool:
        """Check if K line is above D line"""
        if self.k_line[-1] is None or self.d_line[-1] is None:
            return False
        return self.k_line[-1] > self.d_line[-1]

    def is_k_crossing_above_d(self) -> bool:
        """Check if K line crossed above D line"""
        if len(self.k_line) < 2 or len(self.d_line) < 2:
            return False
        if self.k_line[-2] is None or self.d_line[-2] is None:
            return False
        return self.k_line[-2] <= self.d_line[-2] and self.k_line[-1] > self.d_line[-1]
