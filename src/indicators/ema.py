"""
EMA (Exponential Moving Average) Indicator
"""

from typing import List
from src.indicators.base import BaseIndicator


class EMA(BaseIndicator):
    """
    EMA (Exponential Moving Average)
    Gives more weight to recent prices
    """

    def calculate(self, closes: List[float]) -> List[float]:
        """
        Calculate EMA
        
        Args:
            closes: List of close prices
        
        Returns:
            List of EMA values
        """
        if len(closes) < self.period:
            return []

        ema_values = []
        multiplier = 2 / (self.period + 1)

        # First EMA is SMA
        sma = sum(closes[:self.period]) / self.period
        ema_values.append(sma)

        # Calculate subsequent EMAs
        for price in closes[self.period:]:
            ema = (price - ema_values[-1]) * multiplier + ema_values[-1]
            ema_values.append(ema)

        # Pad initial values
        ema_values = [None] * (self.period - 1) + ema_values

        self.values = [x for x in ema_values if x is not None]
        return self.values

    def is_price_above(self, price: float) -> bool:
        """Check if price is above EMA"""
        return self.latest_value is not None and price > self.latest_value

    def is_price_below(self, price: float) -> bool:
        """Check if price is below EMA"""
        return self.latest_value is not None and price < self.latest_value
