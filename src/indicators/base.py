"""
Base Indicator Class
Abstract base for all technical indicators
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from src.data.models import CandleList


class BaseIndicator(ABC):
    """
    Abstract base class for all technical indicators
    """

    def __init__(self, period: int = 14):
        """
        Initialize indicator
        
        Args:
            period: Look-back period for indicator calculation
        """
        self.period = period
        self.values: List[float] = []

    @abstractmethod
    def calculate(self, closes: List[float]) -> List[float]:
        """
        Calculate indicator values
        
        Args:
            closes: List of close prices
        
        Returns:
            List of indicator values
        """
        pass

    def calculate_from_candles(self, candle_list: CandleList) -> List[float]:
        """Calculate from CandleList object"""
        return self.calculate(candle_list.closes)

    @property
    def latest_value(self) -> Optional[float]:
        """Get the latest indicator value"""
        return self.values[-1] if self.values else None

    @property
    def previous_value(self) -> Optional[float]:
        """Get the previous indicator value"""
        return self.values[-2] if len(self.values) >= 2 else None

    def is_ready(self) -> bool:
        """Check if indicator has enough data"""
        return len(self.values) >= self.period
