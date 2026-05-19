"""
MACD (Moving Average Convergence Divergence) Indicator
"""

from typing import List, Dict
from src.indicators.base import BaseIndicator


class MACD(BaseIndicator):
    """
    MACD (Moving Average Convergence Divergence)
    
    Standard settings:
    - Fast period: 12
    - Slow period: 26
    - Signal period: 9
    """

    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        """
        Initialize MACD
        
        Args:
            fast_period: Fast EMA period (default 12)
            slow_period: Slow EMA period (default 26)
            signal_period: Signal line EMA period (default 9)
        """
        super().__init__(slow_period)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.macd_line: List[float] = []
        self.signal_line: List[float] = []
        self.histogram: List[float] = []

    def _calculate_ema(self, data: List[float], period: int) -> List[float]:
        """Calculate EMA"""
        if len(data) < period:
            return []

        ema_values = []
        multiplier = 2 / (period + 1)

        # Simple average for the first value
        sma = sum(data[:period]) / period
        ema_values.append(sma)

        # Calculate subsequent EMAs
        for price in data[period:]:
            ema = (price - ema_values[-1]) * multiplier + ema_values[-1]
            ema_values.append(ema)

        return ema_values

    def calculate(self, closes: List[float]) -> List[float]:
        """
        Calculate MACD values
        
        Args:
            closes: List of close prices
        
        Returns:
            List of MACD histogram values
        """
        if len(closes) < self.slow_period:
            return []

        # Calculate EMAs
        fast_ema = self._calculate_ema(closes, self.fast_period)
        slow_ema = self._calculate_ema(closes, self.slow_period)

        # Align the EMAs (slow_ema starts later)
        min_len = min(len(fast_ema), len(slow_ema))
        fast_ema = fast_ema[-min_len:]
        slow_ema = slow_ema[-min_len:]

        # Calculate MACD line
        macd_line = [fast - slow for fast, slow in zip(fast_ema, slow_ema)]

        # Calculate signal line (EMA of MACD)
        if len(macd_line) < self.signal_period:
            return []

        signal_ema = self._calculate_ema(macd_line, self.signal_period)

        # Calculate histogram
        histogram = []
        for i in range(len(signal_ema)):
            hist = macd_line[len(macd_line) - len(signal_ema) + i] - signal_ema[i]
            histogram.append(hist)

        self.macd_line = macd_line
        self.signal_line = signal_ema
        self.histogram = histogram
        self.values = histogram

        return histogram

    def get_macd_values(self) -> Dict[str, List[float]]:
        """Get all MACD components"""
        return {
            "macd_line": self.macd_line,
            "signal_line": self.signal_line,
            "histogram": self.histogram
        }

    def is_bullish_crossover(self) -> bool:
        """Check if MACD crossed above signal line"""
        if len(self.histogram) < 2:
            return False
        return self.histogram[-2] <= 0 and self.histogram[-1] > 0

    def is_bearish_crossover(self) -> bool:
        """Check if MACD crossed below signal line"""
        if len(self.histogram) < 2:
            return False
        return self.histogram[-2] >= 0 and self.histogram[-1] < 0
