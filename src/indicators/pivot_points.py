"""
Pivot Points Indicator

Classic pivot points calculated from previous period's (daily) OHLC data.

Support levels: S1, S2, S3 — used for SL placement
Resistance levels: R1, R2, R3 — used for TP targets

Also includes Camarilla pivot points which are tighter and more precise
for intraday/short-term crypto trading.
"""

from __future__ import annotations


from typing import Dict, Optional, List, Tuple


class PivotPoints:
    """
    Classic and Camarilla pivot point calculator.

    Used for:
    - Dynamic support/resistance identification
    - TP levels (R1, R2, R3 for longs)
    - SL levels (S1, S2, S3 as stop candidates)
    """

    def calculate_classic(self, prev_high: float, prev_low: float, prev_close: float) -> Dict[str, float]:
        """
        Calculate classic pivot points.

        Formula:
        PP = (High + Low + Close) / 3
        R1 = 2*PP - Low,  S1 = 2*PP - High
        R2 = PP + (High - Low),  S2 = PP - (High - Low)
        R3 = High + 2*(PP - Low),  S3 = Low - 2*(High - PP)

        Returns:
            Dict with PP, R1, R2, R3, S1, S2, S3
        """
        pp = (prev_high + prev_low + prev_close) / 3.0
        diff = prev_high - prev_low

        return {
            "PP": round(pp, 6),
            "R1": round(2 * pp - prev_low, 6),
            "R2": round(pp + diff, 6),
            "R3": round(prev_high + 2 * (pp - prev_low), 6),
            "S1": round(2 * pp - prev_high, 6),
            "S2": round(pp - diff, 6),
            "S3": round(prev_low - 2 * (prev_high - pp), 6),
        }

    def calculate_camarilla(self, prev_high: float, prev_low: float, prev_close: float) -> Dict[str, float]:
        """
        Calculate Camarilla pivot points.

        Camarilla pivots are tighter than classic, very effective for scalping
        and short-term crypto trades.

        H4/L4 = breakout levels (strongest)
        H3/L3 = reversal levels (most actionable)
        """
        diff = prev_high - prev_low
        return {
            "H4": round(prev_close + diff * 1.1 / 2, 6),
            "H3": round(prev_close + diff * 1.1 / 4, 6),
            "H2": round(prev_close + diff * 1.1 / 6, 6),
            "H1": round(prev_close + diff * 1.1 / 12, 6),
            "L1": round(prev_close - diff * 1.1 / 12, 6),
            "L2": round(prev_close - diff * 1.1 / 6, 6),
            "L3": round(prev_close - diff * 1.1 / 4, 6),
            "L4": round(prev_close - diff * 1.1 / 2, 6),
        }

    def get_nearest_support(self, price: float, levels: Dict[str, float]) -> Optional[Tuple[str, float]]:
        """Find the nearest support level below current price."""
        supports = {k: v for k, v in levels.items() if v < price and k.startswith("S") or k.startswith("L")}
        if not supports:
            return None
        nearest = max(supports.values())
        label = [k for k, v in supports.items() if v == nearest][0]
        return (label, nearest)

    def get_nearest_resistance(self, price: float, levels: Dict[str, float]) -> Optional[Tuple[str, float]]:
        """Find the nearest resistance level above current price."""
        resists = {k: v for k, v in levels.items() if v > price and (k.startswith("R") or k.startswith("H"))}
        if not resists:
            return None
        nearest = min(resists.values())
        label = [k for k, v in resists.items() if v == nearest][0]
        return (label, nearest)

    def get_tp_levels(self, price: float, direction: str, method: str = "classic") -> List[Tuple[str, float]]:
        """
        Not directly calculated here — call calculate_* first, then use this helper
        with the resulting levels dict.
        """
        raise NotImplementedError("Call calculate_classic() or calculate_camarilla() first, then filter manually.")

    def get_composite_levels(
        self,
        prev_high: float,
        prev_low: float,
        prev_close: float,
    ) -> Dict[str, Dict[str, float]]:
        """Get both classic and Camarilla levels in one call."""
        return {
            "classic": self.calculate_classic(prev_high, prev_low, prev_close),
            "camarilla": self.calculate_camarilla(prev_high, prev_low, prev_close),
        }

    def get_atr_adjusted_tp(
        self,
        entry: float,
        levels: Dict[str, float],
        direction: str = "long",
        atr: float = 0.0,
        atr_buffer: float = 0.5,
    ) -> List[Tuple[str, float]]:
        """
        Get TP levels from pivot points, adjusted inward by ATR buffer
        to account for price not hitting exact levels.
        """
        result = []
        if direction == "long":
            candidates = sorted(
                [(k, v) for k, v in levels.items() if v > entry],
                key=lambda x: x[1]
            )
            for label, price in candidates:
                adjusted = price - (atr * atr_buffer)
                if adjusted > entry:
                    result.append((label, round(adjusted, 6)))
        else:
            candidates = sorted(
                [(k, v) for k, v in levels.items() if v < entry],
                key=lambda x: x[1],
                reverse=True
            )
            for label, price in candidates:
                adjusted = price + (atr * atr_buffer)
                if adjusted < entry:
                    result.append((label, round(adjusted, 6)))
        return result
