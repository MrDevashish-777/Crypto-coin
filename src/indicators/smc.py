"""
Smart Money Concepts (SMC) Indicators
Calculates Fair Value Gaps (FVG) and Order Blocks (OB) directly from OHLCV data.
"""

from typing import List, Dict, Optional
from src.indicators.base import BaseIndicator
from src.data.models import CandleList

class SMC(BaseIndicator):
    """
    Smart Money Concepts indicator.
    Identifies:
    1. Fair Value Gaps (FVG)
    2. Order Blocks (OB)
    3. Liquidity Sweeps (Sweeps)
    4. Change of Character (ChoCh)
    """

    def __init__(self, period: int = 14):
        super().__init__(period)
        self.fvgs = []
        self.order_blocks = []
        self.sweeps = []
        self.choch = []

    def calculate_from_ohlc(
        self,
        opens: List[float],
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float]
    ) -> Dict[str, List[Dict]]:
        """
        Calculate SMC features.
        Returns a dict of recent FVGs, OBs, Sweeps, and ChoCh.
        """
        if len(closes) < 5:
            return {"fvgs": [], "order_blocks": [], "sweeps": [], "choch": []}

        fvgs = []
        order_blocks = []
        sweeps = []
        choch = []

        # Calculate FVGs (requires 3 candles)
        # Bullish FVG: Low of candle 3 is higher than High of candle 1
        # Bearish FVG: High of candle 3 is lower than Low of candle 1
        for i in range(2, len(closes)):
            # Bullish FVG
            if lows[i] > highs[i-2] and closes[i-1] > opens[i-1]:
                gap_bottom = highs[i-2]
                gap_top = lows[i]
                fvgs.append({
                    "type": "bullish",
                    "top": gap_top,
                    "bottom": gap_bottom,
                    "index": i-1,
                    "active": True
                })
            
            # Bearish FVG
            elif highs[i] < lows[i-2] and closes[i-1] < opens[i-1]:
                gap_top = lows[i-2]
                gap_bottom = highs[i]
                fvgs.append({
                    "type": "bearish",
                    "top": gap_top,
                    "bottom": gap_bottom,
                    "index": i-1,
                    "active": True
                })

        # Calculate Order Blocks (OB)
        # Bullish OB: The last down candle before a strong up move
        # Bearish OB: The last up candle before a strong down move
        
        # Simple detection: look for a large move (e.g. > 1.5x average body size)
        bodies = [abs(closes[j] - opens[j]) for j in range(len(closes))]
        avg_body = sum(bodies) / len(bodies) if bodies else 0

        for i in range(1, len(closes)):
            body = abs(closes[i] - opens[i])
            if body > avg_body * 1.5:  # Strong move
                if closes[i] > opens[i]:  # Strong Bullish move
                    # Look back for the last down candle
                    for j in range(i-1, max(-1, i-5), -1):
                        if closes[j] < opens[j]:
                            order_blocks.append({
                                "type": "bullish",
                                "top": max(opens[j], closes[j]),
                                "bottom": lows[j],
                                "index": j,
                                "active": True
                            })
                            break
                elif closes[i] < opens[i]:  # Strong Bearish move
                    # Look back for the last up candle
                    for j in range(i-1, max(-1, i-5), -1):
                        if closes[j] > opens[j]:
                            order_blocks.append({
                                "type": "bearish",
                                "bottom": min(opens[j], closes[j]),
                                "top": highs[j],
                                "index": j,
                                "active": True
                            })
                            break

        # Detect Swing Highs and Lows for Sweeps & ChoCh
        swing_highs = []
        swing_lows = []
        for i in range(2, len(closes) - 2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                swing_highs.append({"index": i, "price": highs[i]})
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                swing_lows.append({"index": i, "price": lows[i]})

        # Detect Liquidity Sweeps
        # A sweep happens when price wicks above a swing high but closes below it (Bearish Sweep / BSSL)
        # Or wicks below a swing low but closes above it (Bullish Sweep / SSSL)
        for i in range(5, len(closes)):
            for sh in swing_highs:
                if sh["index"] < i - 1 and highs[i] > sh["price"] and closes[i] < sh["price"]:
                    sweeps.append({
                        "type": "bearish_sweep",
                        "price": sh["price"],
                        "index": i,
                        "active": True
                    })
            for sl in swing_lows:
                if sl["index"] < i - 1 and lows[i] < sl["price"] and closes[i] > sl["price"]:
                    sweeps.append({
                        "type": "bullish_sweep",
                        "price": sl["price"],
                        "index": i,
                        "active": True
                    })

        # Detect Change of Character (ChoCh)
        # ChoCh happens when a recent swing high/low is broken with a solid close
        for i in range(5, len(closes)):
            for sh in swing_highs[-3:]:  # Check recent swing highs
                if sh["index"] < i - 1 and closes[i] > sh["price"] and opens[i] < sh["price"]:
                    choch.append({
                        "type": "bullish_choch",
                        "price": sh["price"],
                        "index": i,
                        "active": True
                    })
            for sl in swing_lows[-3:]:  # Check recent swing lows
                if sl["index"] < i - 1 and closes[i] < sl["price"] and opens[i] > sl["price"]:
                    choch.append({
                        "type": "bearish_choch",
                        "price": sl["price"],
                        "index": i,
                        "active": True
                    })

        self.fvgs = fvgs
        self.order_blocks = order_blocks
        self.sweeps = sweeps
        self.choch = choch

        return {
            "fvgs": fvgs,
            "order_blocks": order_blocks,
            "sweeps": sweeps,
            "choch": choch
        }

    def calculate(self, closes: List[float]) -> List[float]:
        raise NotImplementedError("Use calculate_from_ohlc() instead")
