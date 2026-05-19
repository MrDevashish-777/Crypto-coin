"""
ADX (Average Directional Index) + DMI Indicator

Measures TREND STRENGTH (not direction):
- ADX < 20: Weak trend / ranging market
- ADX 20-25: Emerging trend
- ADX > 25: Strong trend
- ADX > 40: Very strong trend

+DI above -DI: Bullish trend
-DI above +DI: Bearish trend

Used by the Market Regime Detector as the primary input.
"""

from __future__ import annotations


from typing import List, Optional, Dict
from src.indicators.base import BaseIndicator


class ADX(BaseIndicator):
    """
    ADX / DMI indicator for trend strength and direction.

    Used for:
    - Market regime detection (trending vs ranging)
    - Filtering signals: only trade in confirmed trends (ADX > 25)
    - Directional bias (+DI vs -DI)
    """

    def __init__(self, period: int = 14):
        super().__init__(period)
        self.plus_di: List[Optional[float]] = []
        self.minus_di: List[Optional[float]] = []
        self.adx_values: List[Optional[float]] = []

    def calculate_from_ohlc(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
    ) -> Dict[str, List[Optional[float]]]:
        """
        Calculate ADX, +DI, -DI from OHLC data.

        Returns:
            Dictionary with: adx, plus_di, minus_di
        """
        n = len(closes)
        if n < self.period + 1:
            return {"adx": [], "plus_di": [], "minus_di": []}

        # Calculate True Range, +DM, -DM
        tr_list, plus_dm, minus_dm = [], [], []
        for i in range(1, n):
            high_diff = highs[i] - highs[i - 1]
            low_diff = lows[i - 1] - lows[i]
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
            tr_list.append(tr)
            plus_dm.append(high_diff if high_diff > low_diff and high_diff > 0 else 0.0)
            minus_dm.append(low_diff if low_diff > high_diff and low_diff > 0 else 0.0)

        # Wilder's smoothed sums
        def wilder_smooth(data: List[float], period: int) -> List[float]:
            if len(data) < period:
                return []
            result = [sum(data[:period])]
            for i in range(period, len(data)):
                result.append(result[-1] - result[-1] / period + data[i])
            return result

        smooth_tr = wilder_smooth(tr_list, self.period)
        smooth_plus = wilder_smooth(plus_dm, self.period)
        smooth_minus = wilder_smooth(minus_dm, self.period)

        # Directional Indicators
        raw_plus_di, raw_minus_di, raw_dx = [], [], []
        for i in range(len(smooth_tr)):
            if smooth_tr[i] == 0:
                raw_plus_di.append(0.0)
                raw_minus_di.append(0.0)
                raw_dx.append(0.0)
            else:
                pdi = 100 * smooth_plus[i] / smooth_tr[i]
                mdi = 100 * smooth_minus[i] / smooth_tr[i]
                raw_plus_di.append(pdi)
                raw_minus_di.append(mdi)
                dx_denom = pdi + mdi
                raw_dx.append(100 * abs(pdi - mdi) / dx_denom if dx_denom != 0 else 0.0)

        # ADX should be Wilder-smoothed average of DX (bounded 0..100),
        # not the running Wilder sum used for TR/DM.
        def wilder_average(data: List[float], period: int) -> List[float]:
            if len(data) < period:
                return []
            avg = sum(data[:period]) / period
            result = [avg]
            for i in range(period, len(data)):
                avg = ((avg * (period - 1)) + data[i]) / period
                result.append(avg)
            return result

        raw_adx = wilder_average(raw_dx, self.period)

        # Pad results to match input length
        offset = n - len(raw_plus_di)
        self.plus_di = [None] * offset + [round(v, 2) for v in raw_plus_di]
        self.minus_di = [None] * offset + [round(v, 2) for v in raw_minus_di]
        adx_offset = n - len(raw_adx)
        self.adx_values = [None] * adx_offset + [round(v, 2) for v in raw_adx]

        self.values = [v for v in self.adx_values if v is not None]
        return {"adx": self.adx_values, "plus_di": self.plus_di, "minus_di": self.minus_di}

    def calculate(self, closes: List[float]) -> List[float]:
        raise NotImplementedError("Use calculate_from_ohlc() for ADX")

    def get_current(self) -> Dict[str, Optional[float]]:
        def last(lst):
            vals = [v for v in lst if v is not None]
            return vals[-1] if vals else None
        return {
            "adx": last(self.adx_values),
            "plus_di": last(self.plus_di),
            "minus_di": last(self.minus_di),
        }

    def is_trending(self, threshold: float = 25.0) -> bool:
        """ADX above threshold = strong trend present."""
        c = self.get_current()
        return c["adx"] is not None and c["adx"] >= threshold

    def is_ranging(self, threshold: float = 20.0) -> bool:
        """ADX below threshold = ranging/choppy market."""
        c = self.get_current()
        return c["adx"] is not None and c["adx"] < threshold

    def is_bullish_trend(self) -> bool:
        """+DI above -DI = bullish directional bias."""
        c = self.get_current()
        if c["plus_di"] is None or c["minus_di"] is None:
            return False
        return c["plus_di"] > c["minus_di"]

    def is_bearish_trend(self) -> bool:
        """-DI above +DI = bearish directional bias."""
        c = self.get_current()
        if c["plus_di"] is None or c["minus_di"] is None:
            return False
        return c["minus_di"] > c["plus_di"]

    def get_trend_strength(self) -> str:
        """Qualitative trend strength label."""
        c = self.get_current()
        adx = c["adx"]
        if adx is None:
            return "unknown"
        if adx < 20:
            return "ranging"
        elif adx < 25:
            return "weak_trend"
        elif adx < 40:
            return "strong_trend"
        else:
            return "very_strong_trend"

    def bullish_di_cross(self) -> bool:
        """+DI just crossed above -DI = bullish momentum signal."""
        pdi = [v for v in self.plus_di if v is not None]
        mdi = [v for v in self.minus_di if v is not None]
        if len(pdi) < 2 or len(mdi) < 2:
            return False
        return pdi[-2] <= mdi[-2] and pdi[-1] > mdi[-1]

    def bearish_di_cross(self) -> bool:
        """-DI just crossed above +DI = bearish momentum signal."""
        pdi = [v for v in self.plus_di if v is not None]
        mdi = [v for v in self.minus_di if v is not None]
        if len(pdi) < 2 or len(mdi) < 2:
            return False
        return mdi[-2] <= pdi[-2] and mdi[-1] > pdi[-1]
