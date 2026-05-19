"""
Bollinger Bands Indicator
"""

from typing import List, Dict, Optional
from src.indicators.base import BaseIndicator
import math


class BollingerBands(BaseIndicator):
    """
    Bollinger Bands
    
    Standard settings:
    - Period: 20
    - Standard deviations: 2
    """

    def __init__(self, period: int = 20, std_devs: float = 2.0):
        """
        Initialize Bollinger Bands
        
        Args:
            period: SMA period (default 20)
            std_devs: Number of standard deviations (default 2)
        """
        super().__init__(period)
        self.std_devs = std_devs
        self.middle_band: List[Optional[float]] = []
        self.upper_band: List[Optional[float]] = []
        self.lower_band: List[Optional[float]] = []
        self.bandwidth: List[float] = []

    def calculate(self, closes: List[float]) -> List[float]:
        """
        Calculate Bollinger Bands
        
        Args:
            closes: List of close prices
        
        Returns:
            List of middle band (SMA) values
        """
        if len(closes) < self.period:
            return []

        self.middle_band = []
        self.upper_band = []
        self.lower_band = []
        self.bandwidth = []

        for i in range(len(closes) - self.period + 1):
            period_closes = closes[i:i + self.period]

            # Calculate SMA (middle band)
            sma = sum(period_closes) / self.period
            self.middle_band.append(sma)

            # Calculate standard deviation
            variance = sum((x - sma) ** 2 for x in period_closes) / self.period
            std_dev = math.sqrt(variance)

            # Calculate upper and lower bands
            upper = sma + (std_dev * self.std_devs)
            lower = sma - (std_dev * self.std_devs)

            self.upper_band.append(upper)
            self.lower_band.append(lower)
            self.bandwidth.append(upper - lower)

        # Pad initial values
        self.middle_band = [None] * (self.period - 1) + self.middle_band
        self.upper_band = [None] * (self.period - 1) + self.upper_band
        self.lower_band = [None] * (self.period - 1) + self.lower_band

        self.values = [x for x in self.middle_band if x is not None]
        return self.values

    def get_bands(self) -> Dict[str, Optional[float]]:
        """Get current bands"""
        return {
            "upper": self.upper_band[-1] if self.upper_band else None,
            "middle": self.middle_band[-1] if self.middle_band else None,
            "lower": self.lower_band[-1] if self.lower_band else None,
            "bandwidth": self.bandwidth[-1] if self.bandwidth else None,
        }

    def is_at_upper_band(self, price: float, tolerance: float = 0.001) -> bool:
        """Check if price is at upper band"""
        if not self.upper_band or self.upper_band[-1] is None:
            return False
        return price >= self.upper_band[-1] * (1 - tolerance)

    def is_at_lower_band(self, price: float, tolerance: float = 0.001) -> bool:
        """Check if price is at lower band"""
        if not self.lower_band or self.lower_band[-1] is None:
            return False
        return price <= self.lower_band[-1] * (1 + tolerance)

    def is_squeezing(self, threshold: float = None) -> bool:
        """Check if bands are squeezing (low volatility)"""
        if not self.bandwidth or len(self.bandwidth) < 2:
            return False

        if threshold is None:
            # Compare current bandwidth to average
            avg_bandwidth = sum(self.bandwidth) / len(self.bandwidth)
            threshold = avg_bandwidth * 0.5

        return self.bandwidth[-1] < threshold

    def is_expanding(self) -> bool:
        """Check if bands are expanding (high volatility)"""
        if len(self.bandwidth) < 2:
            return False
        return self.bandwidth[-1] > self.bandwidth[-2]
