"""
ATR (Average True Range) Indicator
"""

from typing import List
from src.indicators.base import BaseIndicator


class ATR(BaseIndicator):
    """
    ATR (Average True Range)
    Measures volatility
    
    Standard settings:
    - Period: 14
    """

    def __init__(self, period: int = 14):
        """Initialize ATR"""
        super().__init__(period)
        self.true_ranges: List[float] = []

    def _calculate_true_range(
        self,
        high: float,
        low: float,
        prev_close: float
    ) -> float:
        """Calculate true range for a period"""
        hl = high - low
        hc = abs(high - prev_close)
        lc = abs(low - prev_close)
        return max(hl, hc, lc)

    def calculate_from_ohlc(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float]
    ) -> List[float]:
        """
        Calculate ATR from OHLC data
        
        Args:
            highs: List of high prices
            lows: List of low prices
            closes: List of close prices
        
        Returns:
            List of ATR values
        """
        if len(highs) < self.period:
            return []

        # Calculate true ranges
        self.true_ranges = []
        for i in range(1, len(closes)):
            tr = self._calculate_true_range(highs[i], lows[i], closes[i - 1])
            self.true_ranges.append(tr)

        # Calculate ATR
        atr_values = []
        
        # First ATR is SMA of TR
        sma_tr = sum(self.true_ranges[:self.period]) / self.period
        atr_values.append(sma_tr)

        # Subsequent ATRs use smoothing
        prev_atr = sma_tr
        for i in range(self.period, len(self.true_ranges)):
            atr = (prev_atr * (self.period - 1) + self.true_ranges[i]) / self.period
            atr_values.append(atr)
            prev_atr = atr

        # Pad initial values
        atr_values = [None] * self.period + atr_values

        self.values = [x for x in atr_values if x is not None]
        return self.values

    def calculate(self, closes: List[float]) -> List[float]:
        """ATR requires OHLC data, not just closes"""
        raise NotImplementedError("Use calculate_from_ohlc() instead")
