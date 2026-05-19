"""
Data Models - Core data structures for OHLCV data
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List


@dataclass
class Candle:
    """Represents a single OHLCV candle"""
    timestamp: int  # Unix timestamp in milliseconds
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_asset_volume: float = 0.0
    number_of_trades: int = 0
    taker_buy_base_asset_volume: float = 0.0
    taker_buy_quote_asset_volume: float = 0.0

    def __post_init__(self):
        """Validate candle data"""
        assert self.high >= self.low, "High must be >= Low"
        assert self.high >= self.open and self.high >= self.close, "High must be >= Open and Close"
        assert self.low <= self.open and self.low <= self.close, "Low must be <= Open and Close"
        assert self.volume >= 0, "Volume must be positive"

    @property
    def hl2(self) -> float:
        """High + Low / 2"""
        return (self.high + self.low) / 2

    @property
    def hlc3(self) -> float:
        """High + Low + Close / 3"""
        return (self.high + self.low + self.close) / 3

    @property
    def ohlc4(self) -> float:
        """Open + High + Low + Close / 4"""
        return (self.open + self.high + self.low + self.close) / 4


@dataclass
class CandleList:
    """List of candles with utility methods"""
    symbol: str
    timeframe: str
    candles: List[Candle]

    def __post_init__(self):
        """Sort candles by timestamp"""
        self.candles.sort(key=lambda c: c.timestamp)

    def __len__(self) -> int:
        return len(self.candles)

    def __getitem__(self, index: int) -> Candle:
        return self.candles[index]

    @property
    def closes(self) -> List[float]:
        """Get all close prices"""
        return [c.close for c in self.candles]

    @property
    def opens(self) -> List[float]:
        """Get all open prices"""
        return [c.open for c in self.candles]

    @property
    def highs(self) -> List[float]:
        """Get all high prices"""
        return [c.high for c in self.candles]

    @property
    def lows(self) -> List[float]:
        """Get all low prices"""
        return [c.low for c in self.candles]

    @property
    def volumes(self) -> List[float]:
        """Get all volumes"""
        return [c.volume for c in self.candles]

    @property
    def latest_candle(self) -> Optional[Candle]:
        """Get the latest candle"""
        return self.candles[-1] if self.candles else None

    @property
    def latest_close(self) -> Optional[float]:
        """Get the latest close price"""
        return self.latest_candle.close if self.latest_candle else None

    def add_candle(self, candle: Candle):
        """Add a candle and maintain order"""
        self.candles.append(candle)
        self.candles.sort(key=lambda c: c.timestamp)

    def get_range(self, start_index: int, end_index: int) -> List[Candle]:
        """Get candles within index range"""
        return self.candles[start_index:end_index]


@dataclass
class IndicatorValues:
    """Container for indicator values"""
    timestamp: int
    indicator_name: str
    value: float
    additional_values: dict = None  # For multi-line indicators like MACD

    def __post_init__(self):
        if self.additional_values is None:
            self.additional_values = {}
