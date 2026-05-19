"""
Fibonacci Retracement and Extension Levels

Auto-detects swing high/low then computes retracement and extension levels.

Retracements: 23.6%, 38.2%, 50%, 61.8%, 78.6%
Extensions:   100%, 127.2%, 161.8%, 200%, 261.8%
"""

from __future__ import annotations


from typing import List, Optional, Dict, Tuple

FIB_RETRACEMENT = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
FIB_EXTENSION = [1.0, 1.272, 1.414, 1.618, 2.0, 2.618]


class FibonacciLevels:
    """Auto-Fibonacci retracement and extension calculator."""

    def __init__(self, swing_lookback: int = 50):
        self.swing_lookback = swing_lookback
        self.swing_high: Optional[float] = None
        self.swing_low: Optional[float] = None
        self.retracements: Dict[str, float] = {}
        self.extensions: Dict[str, float] = {}
        self.trend: str = "up"

    def _detect_trend(self, closes: List[float]) -> str:
        if len(closes) < 2:
            return "up"
        mid = len(closes) // 2
        return "up" if sum(closes[mid:]) / len(closes[mid:]) > sum(closes[:mid]) / mid else "down"

    def calculate_from_ohlc(self, highs: List[float], lows: List[float], closes: List[float]) -> Dict:
        """Calculate Fibonacci levels from OHLC data."""
        lookback = min(self.swing_lookback, len(highs))
        if lookback < 5:
            return {"retracements": {}, "extensions": {}, "swing_high": None, "swing_low": None}

        self.swing_high = max(highs[-lookback:])
        self.swing_low = min(lows[-lookback:])
        self.trend = self._detect_trend(closes)
        diff = self.swing_high - self.swing_low

        if self.trend == "up":
            self.retracements = {f"{round(r*100,1)}%": round(self.swing_high - diff * r, 6) for r in FIB_RETRACEMENT}
            self.extensions = {f"{round(e*100,1)}%": round(self.swing_low + diff * e, 6) for e in FIB_EXTENSION}
        else:
            self.retracements = {f"{round(r*100,1)}%": round(self.swing_low + diff * r, 6) for r in FIB_RETRACEMENT}
            self.extensions = {f"{round(e*100,1)}%": round(self.swing_high - diff * e, 6) for e in FIB_EXTENSION}

        return {"retracements": self.retracements, "extensions": self.extensions,
                "swing_high": self.swing_high, "swing_low": self.swing_low, "trend": self.trend}

    def get_nearest_retracement(self, price: float) -> Tuple[str, float, float]:
        if not self.retracements:
            return ("50.0%", price, 0.0)
        nearest = min(self.retracements.items(), key=lambda kv: abs(kv[1] - price))
        return (nearest[0], nearest[1], abs(nearest[1] - price) / price * 100)

    def get_fib_sl(self, entry: float, direction: str = "long") -> Optional[float]:
        """78.6% retracement as aggressive SL level."""
        level = self.retracements.get("78.6%")
        if level is None:
            return None
        if direction == "long" and level < entry:
            return level
        elif direction == "short" and level > entry:
            return level
        return None

    def get_fib_tp1(self) -> Optional[float]:
        """161.8% extension as primary TP."""
        return self.extensions.get("161.8%")

    def get_fib_tp2(self) -> Optional[float]:
        """200% extension as secondary TP."""
        return self.extensions.get("200.0%")

    def get_closest_support(self, price: float) -> Optional[float]:
        """Find closest retracement level below current price."""
        below = {k: v for k, v in self.retracements.items() if v < price}
        if not below:
            return None
        return max(below.values())

    def get_closest_resistance(self, price: float) -> Optional[float]:
        """Find closest extension level above current price."""
        above = {k: v for k, v in self.extensions.items() if v > price}
        if not above:
            return None
        return min(above.values())
