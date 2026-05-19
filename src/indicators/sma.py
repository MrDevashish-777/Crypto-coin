"""
SMA (Simple Moving Average) Indicator
"""

from typing import List
from src.indicators.base import BaseIndicator


class SMA(BaseIndicator):
    """
    SMA (Simple Moving Average)
    """

    def calculate(self, closes: List[float]) -> List[float]:
        """
        Calculate SMA
        
        Args:
            closes: List of close prices
        
        Returns:
            List of SMA values
        """
        if len(closes) < self.period:
            return []

        sma_values = []
        for i in range(len(closes) - self.period + 1):
            sma = sum(closes[i:i + self.period]) / self.period
            sma_values.append(sma)

        # Pad initial values
        sma_values = [None] * (self.period - 1) + sma_values

        self.values = [x for x in sma_values if x is not None]
        return self.values

    def is_price_above(self, price: float) -> bool:
        """Check if price is above SMA"""
        return self.latest_value is not None and price > self.latest_value

    def is_price_below(self, price: float) -> bool:
        """Check if price is below SMA"""
        return self.latest_value is not None and price < self.latest_value
