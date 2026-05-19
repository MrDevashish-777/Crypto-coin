"""
Ichimoku Kinko Hyo (Ichimoku Cloud) Indicator

Components:
- Tenkan-sen (Conversion Line): (9-period high + 9-period low) / 2
- Kijun-sen (Base Line): (26-period high + 26-period low) / 2
- Senkou Span A (Leading Span A): (Tenkan + Kijun) / 2, shifted 26 periods ahead
- Senkou Span B (Leading Span B): (52-period high + 52-period low) / 2, shifted 26 periods ahead
- Chikou Span (Lagging Span): Current close, shifted 26 periods back
"""

from __future__ import annotations


from typing import List, Optional, Dict, Tuple
from src.indicators.base import BaseIndicator


class Ichimoku(BaseIndicator):
    """
    Ichimoku Cloud indicator for trend direction, momentum, and support/resistance.

    Trading signals:
    - Price above cloud + Tenkan crosses above Kijun = Strong BUY
    - Price below cloud + Tenkan crosses below Kijun = Strong SELL
    - Cloud twist (Span A crosses Span B) = Trend change warning
    """

    def __init__(
        self,
        tenkan_period: int = 9,
        kijun_period: int = 26,
        senkou_b_period: int = 52,
        displacement: int = 26,
    ):
        super().__init__(senkou_b_period)
        self.tenkan_period = tenkan_period
        self.kijun_period = kijun_period
        self.senkou_b_period = senkou_b_period
        self.displacement = displacement

        # Computed lines
        self.tenkan: List[Optional[float]] = []
        self.kijun: List[Optional[float]] = []
        self.senkou_a: List[Optional[float]] = []
        self.senkou_b: List[Optional[float]] = []
        self.chikou: List[Optional[float]] = []

    def _midpoint(self, highs: List[float], lows: List[float], period: int, idx: int) -> Optional[float]:
        """Calculate midpoint over a period ending at idx."""
        if idx < period - 1:
            return None
        period_highs = highs[idx - period + 1 : idx + 1]
        period_lows = lows[idx - period + 1 : idx + 1]
        return (max(period_highs) + min(period_lows)) / 2.0

    def calculate_from_ohlc(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
    ) -> Dict[str, List[Optional[float]]]:
        """
        Calculate all Ichimoku components from OHLC data.

        Returns:
            Dictionary with keys: tenkan, kijun, senkou_a, senkou_b, chikou
        """
        n = len(closes)
        if n < self.senkou_b_period:
            return {"tenkan": [], "kijun": [], "senkou_a": [], "senkou_b": [], "chikou": []}

        self.tenkan = [self._midpoint(highs, lows, self.tenkan_period, i) for i in range(n)]
        self.kijun = [self._midpoint(highs, lows, self.kijun_period, i) for i in range(n)]

        # Senkou Span A = (Tenkan + Kijun) / 2, plotted displacement bars ahead
        self.senkou_a = [None] * n
        for i in range(n):
            if self.tenkan[i] is not None and self.kijun[i] is not None:
                future_idx = i + self.displacement
                if future_idx < n:
                    self.senkou_a[future_idx] = (self.tenkan[i] + self.kijun[i]) / 2.0

        # Senkou Span B = midpoint of senkou_b_period, plotted displacement bars ahead
        self.senkou_b = [None] * n
        for i in range(n):
            mid = self._midpoint(highs, lows, self.senkou_b_period, i)
            if mid is not None:
                future_idx = i + self.displacement
                if future_idx < n:
                    self.senkou_b[future_idx] = mid

        # Chikou Span = close shifted displacement periods back
        self.chikou = [None] * n
        for i in range(n):
            past_idx = i - self.displacement
            if past_idx >= 0:
                self.chikou[i] = closes[past_idx]

        self.values = [t for t in self.tenkan if t is not None]
        return {
            "tenkan": self.tenkan,
            "kijun": self.kijun,
            "senkou_a": self.senkou_a,
            "senkou_b": self.senkou_b,
            "chikou": self.chikou,
        }

    def calculate(self, closes: List[float]) -> List[float]:
        raise NotImplementedError("Use calculate_from_ohlc() for Ichimoku")

    def get_current(self) -> Dict[str, Optional[float]]:
        """Get latest values of all components."""
        def last(lst):
            vals = [v for v in lst if v is not None]
            return vals[-1] if vals else None

        return {
            "tenkan": last(self.tenkan),
            "kijun": last(self.kijun),
            "senkou_a": last(self.senkou_a),
            "senkou_b": last(self.senkou_b),
            "chikou": last(self.chikou),
        }

    def is_price_above_cloud(self, price: float) -> bool:
        """Check if price is above the Kumo cloud (bullish zone)."""
        c = self.get_current()
        if c["senkou_a"] is None or c["senkou_b"] is None:
            return False
        cloud_top = max(c["senkou_a"], c["senkou_b"])
        return price > cloud_top

    def is_price_below_cloud(self, price: float) -> bool:
        """Check if price is below the Kumo cloud (bearish zone)."""
        c = self.get_current()
        if c["senkou_a"] is None or c["senkou_b"] is None:
            return False
        cloud_bottom = min(c["senkou_a"], c["senkou_b"])
        return price < cloud_bottom

    def is_cloud_bullish(self) -> bool:
        """Senkou Span A > Senkou Span B = bullish cloud."""
        c = self.get_current()
        if c["senkou_a"] is None or c["senkou_b"] is None:
            return False
        return c["senkou_a"] > c["senkou_b"]

    def is_tenkan_above_kijun(self) -> bool:
        """Tenkan above Kijun = bullish momentum."""
        c = self.get_current()
        if c["tenkan"] is None or c["kijun"] is None:
            return False
        return c["tenkan"] > c["kijun"]

    def bullish_tk_cross(self) -> bool:
        """Tenkan just crossed above Kijun (bullish signal)."""
        if len(self.tenkan) < 2 or len(self.kijun) < 2:
            return False
        t_vals = [v for v in self.tenkan if v is not None]
        k_vals = [v for v in self.kijun if v is not None]
        if len(t_vals) < 2 or len(k_vals) < 2:
            return False
        # Previous bar: tenkan <= kijun, current bar: tenkan > kijun
        prev_bull = t_vals[-2] <= k_vals[-2]
        curr_bull = t_vals[-1] > k_vals[-1]
        return prev_bull and curr_bull

    def bearish_tk_cross(self) -> bool:
        """Tenkan just crossed below Kijun (bearish signal)."""
        if len(self.tenkan) < 2 or len(self.kijun) < 2:
            return False
        t_vals = [v for v in self.tenkan if v is not None]
        k_vals = [v for v in self.kijun if v is not None]
        if len(t_vals) < 2 or len(k_vals) < 2:
            return False
        prev_bear = t_vals[-2] >= k_vals[-2]
        curr_bear = t_vals[-1] < k_vals[-1]
        return prev_bear and curr_bear

    def get_cloud_support_resistance(self) -> Tuple[Optional[float], Optional[float]]:
        """Returns (support, resistance) from the current cloud."""
        c = self.get_current()
        if c["senkou_a"] is None or c["senkou_b"] is None:
            return None, None
        top = max(c["senkou_a"], c["senkou_b"])
        bottom = min(c["senkou_a"], c["senkou_b"])
        return bottom, top  # (support, resistance)

    def bullish_signal_strength(self, price: float) -> float:
        """
        Returns a score from 0.0 to 1.0 representing overall bullish strength.
        Based on: above cloud, cloud bullish, TK cross up, chikou above
        """
        score = 0.0
        if self.is_price_above_cloud(price):
            score += 0.35
        if self.is_cloud_bullish():
            score += 0.25
        if self.is_tenkan_above_kijun():
            score += 0.25
        if self.bullish_tk_cross():
            score += 0.15
        return min(score, 1.0)

    def bearish_signal_strength(self, price: float) -> float:
        """Returns a score from 0.0 to 1.0 representing overall bearish strength."""
        score = 0.0
        if self.is_price_below_cloud(price):
            score += 0.35
        if not self.is_cloud_bullish():
            score += 0.25
        if not self.is_tenkan_above_kijun():
            score += 0.25
        if self.bearish_tk_cross():
            score += 0.15
        return min(score, 1.0)
