"""
Supertrend Indicator

ATR-based trend-following indicator that dynamically adapts to market volatility.
When price closes above the Supertrend line, trend is BULLISH (+1).
When price closes below the Supertrend line, trend is BEARISH (-1).

The Supertrend line itself acts as a dynamic trailing stop loss.
"""

from __future__ import annotations


from typing import List, Optional, Tuple, Dict
from src.indicators.base import BaseIndicator


class Supertrend(BaseIndicator):
    """
    Supertrend indicator for adaptive trend detection and dynamic stop-loss.

    Formula:
    - Upper Band = (high + low) / 2 + multiplier * ATR
    - Lower Band = (high + low) / 2 - multiplier * ATR
    - Supertrend follows the lower band in uptrend, upper band in downtrend

    Used by:
    - Supertrend Strategy (primary)
    - Confluence Strategy (trend filter)
    - Market Regime Detector (trend confirmation)
    """

    def __init__(self, atr_period: int = 10, multiplier: float = 3.0):
        """
        Initialize Supertrend.

        Args:
            atr_period: ATR calculation period (default 10)
            multiplier: ATR multiplier for band width (default 3.0)
        """
        super().__init__(atr_period)
        self.multiplier = multiplier
        self.supertrend: List[Optional[float]] = []
        self.trend: List[int] = []  # +1 = bullish, -1 = bearish
        self.upper_band: List[Optional[float]] = []
        self.lower_band: List[Optional[float]] = []

    def _calculate_atr(self, highs: List[float], lows: List[float], closes: List[float]) -> List[float]:
        """Calculate ATR using Wilder's smoothing method."""
        tr_list = []
        for i in range(1, len(closes)):
            hl = highs[i] - lows[i]
            hc = abs(highs[i] - closes[i - 1])
            lc = abs(lows[i] - closes[i - 1])
            tr_list.append(max(hl, hc, lc))

        if not tr_list:
            return []

        # First ATR is simple average
        atr_list = []
        if len(tr_list) >= self.period:
            first_atr = sum(tr_list[:self.period]) / self.period
            atr_list.append(first_atr)
            for i in range(self.period, len(tr_list)):
                atr = (atr_list[-1] * (self.period - 1) + tr_list[i]) / self.period
                atr_list.append(atr)

        return atr_list

    def calculate_from_ohlc(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
    ) -> Dict[str, List]:
        """
        Calculate Supertrend from OHLC data.

        Returns:
            Dictionary with: supertrend, trend (+1/-1), upper_band, lower_band
        """
        n = len(closes)
        if n < self.period + 1:
            return {"supertrend": [], "trend": [], "upper_band": [], "lower_band": []}

        atr_list = self._calculate_atr(highs, lows, closes)
        # ATR starts from index `period` (there's an offset due to TR needing previous close)
        atr_offset = self.period  # first ATR value corresponds to closes[atr_offset]

        self.supertrend = [None] * n
        self.trend = [0] * n
        self.upper_band = [None] * n
        self.lower_band = [None] * n

        prev_upper = None
        prev_lower = None
        prev_trend = 1

        for i in range(atr_offset, n):
            atr_idx = i - atr_offset
            if atr_idx >= len(atr_list):
                break
            atr = atr_list[atr_idx]
            hl2 = (highs[i] + lows[i]) / 2.0

            basic_upper = hl2 + (self.multiplier * atr)
            basic_lower = hl2 - (self.multiplier * atr)

            # Final upper band
            if prev_upper is None:
                final_upper = basic_upper
            else:
                final_upper = min(basic_upper, prev_upper) if closes[i - 1] <= prev_upper else basic_upper

            # Final lower band
            if prev_lower is None:
                final_lower = basic_lower
            else:
                final_lower = max(basic_lower, prev_lower) if closes[i - 1] >= prev_lower else basic_lower

            self.upper_band[i] = final_upper
            self.lower_band[i] = final_lower

            # Determine trend
            if closes[i] > final_upper:
                current_trend = 1  # Bullish
            elif closes[i] < final_lower:
                current_trend = -1  # Bearish
            else:
                current_trend = prev_trend  # Continue previous trend

            self.trend[i] = current_trend

            if current_trend == 1:
                self.supertrend[i] = final_lower
            else:
                self.supertrend[i] = final_upper

            prev_upper = final_upper
            prev_lower = final_lower
            prev_trend = current_trend

        self.values = [v for v in self.supertrend if v is not None]
        return {
            "supertrend": self.supertrend,
            "trend": self.trend,
            "upper_band": self.upper_band,
            "lower_band": self.lower_band,
        }

    def calculate(self, closes: List[float]) -> List[float]:
        raise NotImplementedError("Use calculate_from_ohlc() for Supertrend")

    def get_current(self) -> Dict[str, Optional]:
        """Get the latest Supertrend values."""
        st_vals = [(i, v) for i, v in enumerate(self.supertrend) if v is not None]
        trend_vals = [v for v in self.trend if v != 0]
        return {
            "supertrend": st_vals[-1][1] if st_vals else None,
            "trend": trend_vals[-1] if trend_vals else 0,
            "upper_band": next((v for v in reversed(self.upper_band) if v is not None), None),
            "lower_band": next((v for v in reversed(self.lower_band) if v is not None), None),
        }

    def is_bullish(self) -> bool:
        """Current trend is bullish (+1)."""
        c = self.get_current()
        return c["trend"] == 1

    def is_bearish(self) -> bool:
        """Current trend is bearish (-1)."""
        c = self.get_current()
        return c["trend"] == -1

    def just_turned_bullish(self) -> bool:
        """Supertrend just flipped from bearish to bullish (buy signal)."""
        active_trends = [v for v in self.trend if v != 0]
        if len(active_trends) < 2:
            return False
        return active_trends[-2] == -1 and active_trends[-1] == 1

    def just_turned_bearish(self) -> bool:
        """Supertrend just flipped from bullish to bearish (sell signal)."""
        active_trends = [v for v in self.trend if v != 0]
        if len(active_trends) < 2:
            return False
        return active_trends[-2] == 1 and active_trends[-1] == -1

    def get_dynamic_stop_loss(self, direction: str = "long") -> Optional[float]:
        """
        Get dynamic stop-loss level from the Supertrend line.
        For long: use supertrend as trailing stop.
        For short: use the upper/lower band.
        """
        c = self.get_current()
        if direction == "long":
            return c["lower_band"]  # bull: SL below lower band
        else:
            return c["upper_band"]  # bear: SL above upper band
