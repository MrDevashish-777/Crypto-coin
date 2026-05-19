"""
RSI (Relative Strength Index) Indicator
"""

from typing import List
from src.indicators.base import BaseIndicator


class RSI(BaseIndicator):
    """
    Relative Strength Index (RSI)
    
    Standard settings:
    - Period: 14
    - Overbought: 70
    - Oversold: 30
    """

    def __init__(self, period: int = 14, overbought: float = 70, oversold: float = 30):
        """
        Initialize RSI
        
        Args:
            period: Lookback period (default 14)
            overbought: Overbought threshold (default 70)
            oversold: Oversold threshold (default 30)
        """
        super().__init__(period)
        self.overbought = overbought
        self.oversold = oversold

    def calculate(self, closes: List[float]) -> List[float]:
        """
        Calculate RSI values
        
        Args:
            closes: List of close prices
        
        Returns:
            List of RSI values (0-100)
        """
        if len(closes) < self.period + 1:
            return []

        rsi_values = []
        prices = closes[:]

        # Calculate price changes
        changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

        # Separate gains and losses
        gains = [max(0, change) for change in changes]
        losses = [abs(min(0, change)) for change in changes]

        # Calculate average gains and losses
        avg_gain = sum(gains[:self.period]) / self.period
        avg_loss = sum(losses[:self.period]) / self.period

        # Calculate RSI for remaining values
        for i in range(self.period, len(changes)):
            avg_gain = (avg_gain * (self.period - 1) + gains[i]) / self.period
            avg_loss = (avg_loss * (self.period - 1) + losses[i]) / self.period

            rs = avg_gain / avg_loss if avg_loss != 0 else 0
            rsi = 100 - (100 / (1 + rs))
            rsi_values.append(rsi)

        # Pad with None for the first period values
        rsi_values = [None] * (self.period) + rsi_values

        self.values = rsi_values
        return rsi_values

    def is_overbought(self) -> bool:
        """Check if RSI is in overbought territory"""
        return self.latest_value is not None and self.latest_value > self.overbought

    def is_oversold(self) -> bool:
        """Check if RSI is in oversold territory"""
        return self.latest_value is not None and self.latest_value < self.oversold

    def is_crossing_above_oversold(self) -> bool:
        """Check if RSI is crossing above oversold level"""
        if self.latest_value is None or self.previous_value is None:
            return False
        return self.previous_value <= self.oversold < self.latest_value

    def is_crossing_below_overbought(self) -> bool:
        """Check if RSI is crossing below overbought level"""
        if self.latest_value is None or self.previous_value is None:
            return False
        return self.previous_value >= self.overbought > self.latest_value
