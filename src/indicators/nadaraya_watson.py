"""
Nadaraya-Watson Envelope (LuxAlgo) — non-repainting endpoint method.

Matches TradingView "Nadaraya-Watson Envelope [LuxAlgo]" with Repainting Smoothing disabled.
Uses Gaussian kernel regression for the midline and an adaptive envelope from mean absolute error.

Signals (mean-reversion at bands):
- Bull: price crosses back above the lower band (was below, now at/above)
- Bear: price crosses back below the upper band (was above, now at/below)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional


def _gauss(x: float, h: float) -> float:
    return math.exp(-(x * x) / (h * h * 2.0))


@dataclass(frozen=True)
class NWESnapshot:
    """Latest envelope values and signal flags."""

    midpoint: float
    upper: float
    lower: float
    mae: float
    bull_bounce: bool
    bear_rejection: bool
    near_lower: bool
    near_upper: bool
    trend_bias: Optional[str]  # "bull" | "bear" | None


class NadarayaWatsonEnvelope:
    """
    Non-repainting Nadaraya-Watson envelope.

    Parameters match Pine defaults: bandwidth=8, multiplier=3, lookback=500.
    """

    def __init__(
        self,
        bandwidth: float = 8.0,
        multiplier: float = 3.0,
        lookback: int = 500,
        mae_period: int = 499,
    ) -> None:
        self.h = max(bandwidth, 0.1)
        self.mult = max(multiplier, 0.0)
        self.lookback = max(lookback, 10)
        self.mae_period = max(mae_period, 10)
        self._coefs = [_gauss(float(i), self.h) for i in range(self.lookback)]

    def _endpoint(self, closes: List[float], t: int) -> float:
        limit = min(self.lookback, t + 1)
        wsum = 0.0
        out = 0.0
        for i in range(limit):
            w = self._coefs[i]
            out += closes[t - i] * w
            wsum += w
        return out / wsum if wsum > 0 else closes[t]

    def calculate(self, closes: List[float]) -> dict[str, List[float]]:
        """
        Compute midpoint, upper, and lower bands for each bar.

        Returns dict with keys: midpoint, upper, lower, mae.
        """
        n = len(closes)
        midpoints: List[float] = []
        uppers: List[float] = []
        lowers: List[float] = []
        maes: List[float] = []
        abs_devs: List[float] = []

        for t in range(n):
            mid = self._endpoint(closes, t)
            midpoints.append(mid)
            abs_devs.append(abs(closes[t] - mid))

        for t in range(n):
            start = max(0, t - self.mae_period + 1)
            window = abs_devs[start : t + 1]
            mae = (sum(window) / len(window)) * self.mult if window else 0.0
            maes.append(mae)
            uppers.append(midpoints[t] + mae)
            lowers.append(midpoints[t] - mae)

        return {
            "midpoint": midpoints,
            "upper": uppers,
            "lower": lowers,
            "mae": maes,
        }

    def snapshot(self, closes: List[float], *, band_touch_pct: float = 0.003) -> Optional[NWESnapshot]:
        """Latest-bar envelope state and crossover signals."""
        if len(closes) < 3:
            return None

        bands = self.calculate(closes)
        mid = bands["midpoint"][-1]
        upper = bands["upper"][-1]
        lower = bands["lower"][-1]
        mae = bands["mae"][-1]

        c0, c1 = closes[-2], closes[-1]
        u0, u1 = bands["upper"][-2], upper
        l0, l1 = bands["lower"][-2], lower

        # Repaint-mode labels: bounce from lower / rejection from upper
        bull_bounce = c0 < l0 and c1 >= l1
        bear_rejection = c0 > u0 and c1 <= u1

        near_lower = lower > 0 and abs(c1 - lower) / lower <= band_touch_pct
        near_upper = upper > 0 and abs(c1 - upper) / upper <= band_touch_pct

        trend_bias: Optional[str] = None
        if c1 > mid:
            trend_bias = "bull"
        elif c1 < mid:
            trend_bias = "bear"

        return NWESnapshot(
            midpoint=mid,
            upper=upper,
            lower=lower,
            mae=mae,
            bull_bounce=bull_bounce,
            bear_rejection=bear_rejection,
            near_lower=near_lower,
            near_upper=near_upper,
            trend_bias=trend_bias,
        )

    def signal_strength(self, snap: NWESnapshot, side: str) -> float:
        """Score 0..1 for how well the snapshot supports BUY or SELL."""
        if side == "BUY":
            if snap.bull_bounce:
                return 0.90
            if snap.near_lower:
                return 0.72
            if snap.trend_bias == "bull" and snap.midpoint > 0:
                dist = (snap.midpoint - snap.lower) / max(snap.mae, 1e-9)
                return min(0.65, 0.45 + dist * 0.08)
        else:
            if snap.bear_rejection:
                return 0.90
            if snap.near_upper:
                return 0.72
            if snap.trend_bias == "bear" and snap.midpoint > 0:
                dist = (snap.upper - snap.midpoint) / max(snap.mae, 1e-9)
                return min(0.65, 0.45 + dist * 0.08)
        return 0.0
