"""
Heikin-Ashi Candle Converter

Heikin-Ashi ("average bar" in Japanese) smooths price noise and
makes trends much easier to see.

Key signals:
- All-green HA candles with no lower shadows = strong uptrend
- All-red HA candles with no upper shadows = strong downtrend
- Small-bodied HA candle = trend indecision / potential reversal
- HA candle color change = early trend reversal signal
"""

from __future__ import annotations


from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class HACandle:
    """A single Heikin-Ashi candle."""
    open: float
    high: float
    low: float
    close: float
    is_bullish: bool  # close > open
    has_lower_shadow: bool  # low < min(open, close)
    has_upper_shadow: bool  # high > max(open, close)
    body_size: float  # abs(close - open)


class HeikinAshi:
    """
    Heikin-Ashi candle transformer.

    Used for:
    - Trend direction filtering (enter only in HA-confirmed trend direction)
    - Reducing false signals from noisy price action
    - Identifying strong trend conditions (no shadow candles)
    """

    def __init__(self):
        self.ha_candles: List[HACandle] = []

    def calculate(
        self,
        opens: List[float],
        highs: List[float],
        lows: List[float],
        closes: List[float],
    ) -> List[HACandle]:
        """
        Convert regular OHLC candles to Heikin-Ashi.

        HA Close = (Open + High + Low + Close) / 4
        HA Open  = (Previous HA Open + Previous HA Close) / 2
        HA High  = max(High, HA Open, HA Close)
        HA Low   = min(Low, HA Open, HA Close)

        Returns:
            List of HACandle objects
        """
        n = len(closes)
        if n == 0:
            return []

        self.ha_candles = []

        # First HA candle bootstraps from regular OHLC
        ha_open = (opens[0] + closes[0]) / 2.0
        ha_close = (opens[0] + highs[0] + lows[0] + closes[0]) / 4.0
        ha_high = max(highs[0], ha_open, ha_close)
        ha_low = min(lows[0], ha_open, ha_close)

        self.ha_candles.append(self._make_ha_candle(ha_open, ha_high, ha_low, ha_close))

        for i in range(1, n):
            prev_ha_open = self.ha_candles[-1].open
            prev_ha_close = self.ha_candles[-1].close

            ha_open = (prev_ha_open + prev_ha_close) / 2.0
            ha_close = (opens[i] + highs[i] + lows[i] + closes[i]) / 4.0
            ha_high = max(highs[i], ha_open, ha_close)
            ha_low = min(lows[i], ha_open, ha_close)

            self.ha_candles.append(self._make_ha_candle(ha_open, ha_high, ha_low, ha_close))

        return self.ha_candles

    def _make_ha_candle(self, o: float, h: float, l: float, c: float) -> HACandle:
        return HACandle(
            open=o, high=h, low=l, close=c,
            is_bullish=c >= o,
            has_lower_shadow=l < min(o, c),
            has_upper_shadow=h > max(o, c),
            body_size=abs(c - o),
        )

    def get_trend(self, lookback: int = 3) -> str:
        """
        Determine trend from last N HA candles.

        Returns: 'bullish', 'bearish', or 'neutral'
        """
        if len(self.ha_candles) < lookback:
            return "neutral"
        recent = self.ha_candles[-lookback:]
        bulls = sum(1 for c in recent if c.is_bullish)
        bears = sum(1 for c in recent if not c.is_bullish)
        if bulls == lookback:
            return "bullish"
        elif bears == lookback:
            return "bearish"
        return "neutral"

    def is_strong_uptrend(self, lookback: int = 3) -> bool:
        """All recent HA candles are bullish with no lower shadows."""
        if len(self.ha_candles) < lookback:
            return False
        recent = self.ha_candles[-lookback:]
        return all(c.is_bullish and not c.has_lower_shadow for c in recent)

    def is_strong_downtrend(self, lookback: int = 3) -> bool:
        """All recent HA candles are bearish with no upper shadows."""
        if len(self.ha_candles) < lookback:
            return False
        recent = self.ha_candles[-lookback:]
        return all(not c.is_bullish and not c.has_upper_shadow for c in recent)

    def is_doji(self) -> bool:
        """Last HA candle is a small-body doji — indecision / reversal warning."""
        if not self.ha_candles:
            return False
        last = self.ha_candles[-1]
        # Doji if body < 30% of high-low range
        hl_range = last.high - last.low
        return hl_range > 0 and last.body_size / hl_range < 0.3

    def just_turned_bullish(self) -> bool:
        """HA candle color just flipped to green."""
        if len(self.ha_candles) < 2:
            return False
        return not self.ha_candles[-2].is_bullish and self.ha_candles[-1].is_bullish

    def just_turned_bearish(self) -> bool:
        """HA candle color just flipped to red."""
        if len(self.ha_candles) < 2:
            return False
        return self.ha_candles[-2].is_bullish and not self.ha_candles[-1].is_bullish

    def get_ha_closes(self) -> List[float]:
        """Get list of HA close prices (smoother than regular closes)."""
        return [c.close for c in self.ha_candles]
