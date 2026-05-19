"""
VWAP (Volume-Weighted Average Price) Indicator

The institutional benchmark for fair value in any given session.
Price above VWAP = bullish bias (buyers in control)
Price below VWAP = bearish bias (sellers in control)

Also includes standard deviation bands (VWAP ± 1σ, ±2σ) for mean-reversion targets.
"""

from __future__ import annotations


from typing import List, Optional, Dict
import math
from src.indicators.base import BaseIndicator


class VWAP(BaseIndicator):
    """
    VWAP indicator with standard deviation bands.

    Used for:
    - Entry confirmation (buy only when price > VWAP)
    - Dynamic intraday support/resistance levels
    - Mean-reversion targets at ±1σ and ±2σ bands
    """

    def __init__(self):
        super().__init__(period=1)  # VWAP doesn't use a fixed period
        self.vwap: List[Optional[float]] = []
        self.upper_band_1: List[Optional[float]] = []
        self.lower_band_1: List[Optional[float]] = []
        self.upper_band_2: List[Optional[float]] = []
        self.lower_band_2: List[Optional[float]] = []

    def calculate_from_ohlcv(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float],
    ) -> Dict[str, List[Optional[float]]]:
        """
        Calculate VWAP and standard deviation bands.

        Args:
            highs, lows, closes: Price data
            volumes: Volume data (must match length)

        Returns:
            Dictionary with vwap, upper/lower bands at 1σ and 2σ
        """
        n = len(closes)
        if n == 0 or len(volumes) != n:
            return {"vwap": [], "upper_1": [], "lower_1": [], "upper_2": [], "lower_2": []}

        self.vwap = []
        self.upper_band_1 = []
        self.lower_band_1 = []
        self.upper_band_2 = []
        self.lower_band_2 = []

        cumulative_pv = 0.0
        cumulative_v = 0.0
        cumulative_pv2 = 0.0  # for variance: Σ(typical_price² * volume)

        for i in range(n):
            tp = (highs[i] + lows[i] + closes[i]) / 3.0
            vol = volumes[i] if volumes[i] > 0 else 1e-9

            cumulative_pv += tp * vol
            cumulative_v += vol
            cumulative_pv2 += (tp ** 2) * vol

            vwap_val = cumulative_pv / cumulative_v
            variance = (cumulative_pv2 / cumulative_v) - (vwap_val ** 2)
            std_dev = math.sqrt(max(variance, 0))

            self.vwap.append(vwap_val)
            self.upper_band_1.append(vwap_val + std_dev)
            self.lower_band_1.append(vwap_val - std_dev)
            self.upper_band_2.append(vwap_val + 2 * std_dev)
            self.lower_band_2.append(vwap_val - 2 * std_dev)

        self.values = list(self.vwap)
        return {
            "vwap": self.vwap,
            "upper_1": self.upper_band_1,
            "lower_1": self.lower_band_1,
            "upper_2": self.upper_band_2,
            "lower_2": self.lower_band_2,
        }

    def calculate(self, closes: List[float]) -> List[float]:
        raise NotImplementedError("Use calculate_from_ohlcv() for VWAP")

    def get_current(self) -> Dict[str, Optional[float]]:
        """Get latest VWAP and band values."""
        def last(lst):
            return lst[-1] if lst else None
        return {
            "vwap": last(self.vwap),
            "upper_1": last(self.upper_band_1),
            "lower_1": last(self.lower_band_1),
            "upper_2": last(self.upper_band_2),
            "lower_2": last(self.lower_band_2),
        }

    def is_price_above_vwap(self, price: float) -> bool:
        """Price is above VWAP — bullish intraday bias."""
        c = self.get_current()
        return c["vwap"] is not None and price > c["vwap"]

    def is_price_at_vwap_support(self, price: float, tolerance: float = 0.002) -> bool:
        """Price is touching VWAP from above — potential long entry."""
        c = self.get_current()
        if c["vwap"] is None:
            return False
        return abs(price - c["vwap"]) / c["vwap"] <= tolerance and price >= c["vwap"]

    def is_price_stretched_above(self, price: float) -> bool:
        """Price is above upper 2σ band — overextended, possible reversion."""
        c = self.get_current()
        return c["upper_2"] is not None and price > c["upper_2"]

    def is_price_stretched_below(self, price: float) -> bool:
        """Price is below lower 2σ band — oversold, possible bounce zone."""
        c = self.get_current()
        return c["lower_2"] is not None and price < c["lower_2"]

    def get_nearest_level(self, price: float) -> Tuple[str, float]:
        """Find the nearest VWAP level to the current price."""
        c = self.get_current()
        levels = {
            "vwap": c["vwap"],
            "upper_1": c["upper_1"],
            "lower_1": c["lower_1"],
            "upper_2": c["upper_2"],
            "lower_2": c["lower_2"],
        }
        valid = {k: v for k, v in levels.items() if v is not None}
        if not valid:
            return "vwap", price
        nearest = min(valid.items(), key=lambda kv: abs(kv[1] - price))
        return nearest


# Fix missing import
from typing import Tuple
