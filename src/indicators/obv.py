"""
OBV (On-Balance Volume) Indicator

Tracks cumulative volume flow. Smart money accumulation/distribution detector.

Rules:
- If today's close > yesterday's close: OBV += today's volume
- If today's close < yesterday's close: OBV -= today's volume
- If today's close == yesterday's close: OBV unchanged

OBV divergence with price = powerful reversal signal:
- Price making new highs but OBV declining = bearish divergence (distribution)
- Price making new lows but OBV rising = bullish divergence (accumulation)
"""

from __future__ import annotations


from typing import List, Optional, Dict
from src.indicators.base import BaseIndicator


class OBV(BaseIndicator):
    """
    On-Balance Volume indicator for volume flow and divergence detection.

    Used for:
    - Confirming breakouts (volume must support price movement)
    - Detecting accumulation/distribution phases
    - Divergence signals (OBV leads price)
    """

    def __init__(self, signal_period: int = 10):
        """
        Initialize OBV.

        Args:
            signal_period: Period for OBV signal line (EMA of OBV, default 10)
        """
        super().__init__(signal_period)
        self.signal_period = signal_period
        self.obv_values: List[float] = []
        self.signal_line: List[Optional[float]] = []

    def calculate_from_cv(
        self,
        closes: List[float],
        volumes: List[float],
    ) -> Dict[str, List]:
        """
        Calculate OBV and its signal line.

        Args:
            closes: List of close prices
            volumes: List of volume values

        Returns:
            Dictionary with: obv (raw), signal (EMA of OBV), trend
        """
        n = len(closes)
        if n < 2 or len(volumes) != n:
            return {"obv": [], "signal": [], "trend": []}

        self.obv_values = [0.0]
        for i in range(1, n):
            if closes[i] > closes[i - 1]:
                self.obv_values.append(self.obv_values[-1] + volumes[i])
            elif closes[i] < closes[i - 1]:
                self.obv_values.append(self.obv_values[-1] - volumes[i])
            else:
                self.obv_values.append(self.obv_values[-1])

        # Signal line = EMA of OBV
        self.signal_line = self._ema(self.obv_values, self.signal_period)

        # Trend: +1 if OBV > signal, -1 if OBV < signal
        trend = []
        for i in range(n):
            if i < len(self.signal_line) and self.signal_line[i] is not None:
                trend.append(1 if self.obv_values[i] > self.signal_line[i] else -1)
            else:
                trend.append(0)

        self.values = self.obv_values
        return {"obv": self.obv_values, "signal": self.signal_line, "trend": trend}

    def _ema(self, data: List[float], period: int) -> List[Optional[float]]:
        """Calculate EMA over a list."""
        result: List[Optional[float]] = [None] * len(data)
        if len(data) < period:
            return result
        k = 2.0 / (period + 1)
        # Seed with SMA
        sma = sum(data[:period]) / period
        result[period - 1] = sma
        for i in range(period, len(data)):
            result[i] = data[i] * k + result[i - 1] * (1 - k)
        return result

    def calculate(self, closes: List[float]) -> List[float]:
        raise NotImplementedError("Use calculate_from_cv() with volumes for OBV")

    def get_current(self) -> Dict[str, Optional[float]]:
        """Get latest OBV and signal values."""
        sig_vals = [v for v in self.signal_line if v is not None]
        return {
            "obv": self.obv_values[-1] if self.obv_values else None,
            "signal": sig_vals[-1] if sig_vals else None,
        }

    def is_bullish_trend(self) -> bool:
        """OBV is above its signal line — bullish volume trend."""
        c = self.get_current()
        if c["obv"] is None or c["signal"] is None:
            return False
        return c["obv"] > c["signal"]

    def is_rising(self, lookback: int = 5) -> bool:
        """OBV has been rising over the last N periods."""
        if len(self.obv_values) < lookback + 1:
            return False
        recent = self.obv_values[-lookback:]
        return recent[-1] > recent[0]

    def is_falling(self, lookback: int = 5) -> bool:
        """OBV has been falling over the last N periods."""
        if len(self.obv_values) < lookback + 1:
            return False
        recent = self.obv_values[-lookback:]
        return recent[-1] < recent[0]

    def bullish_divergence(self, closes: List[float], lookback: int = 20) -> bool:
        """
        Bullish divergence: price making lower lows but OBV making higher lows.
        Indicates smart money accumulating.
        """
        if len(closes) < lookback or len(self.obv_values) < lookback:
            return False
        price_lower = closes[-1] < min(closes[-lookback:-1])
        obv_higher = self.obv_values[-1] > min(self.obv_values[-lookback:-1])
        return price_lower and obv_higher

    def bearish_divergence(self, closes: List[float], lookback: int = 20) -> bool:
        """
        Bearish divergence: price making higher highs but OBV making lower highs.
        Indicates smart money distributing.
        """
        if len(closes) < lookback or len(self.obv_values) < lookback:
            return False
        price_higher = closes[-1] > max(closes[-lookback:-1])
        obv_lower = self.obv_values[-1] < max(self.obv_values[-lookback:-1])
        return price_higher and obv_lower

    def volume_confirms_breakout(self, price_broke_high: bool) -> bool:
        """Volume confirms a price breakout when OBV is also rising."""
        return price_broke_high and self.is_rising(lookback=3)
