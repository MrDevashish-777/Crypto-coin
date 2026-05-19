"""
Smart Money Strategy (Institutional Grade)
Uses FVGs and Order Blocks to find high-probability setups.
"""

from typing import Optional, Dict
from src.data.models import CandleList
from src.signals.signal import TradingSignal, SignalType
from src.signals.strategies.base import BaseStrategy
from src.indicators.smc import SMC
from src.indicators.atr import ATR
from src.risk.risk_manager import RiskManager
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class SmartMoneyStrategy(BaseStrategy):
    """
    Identifies high-probability setups using Smart Money Concepts:
    - Order Blocks (OB)
    - Fair Value Gaps (FVG)
    """

    def __init__(self, timeframe: str = "1h"):
        super().__init__(name="Smart Money Strategy", min_confidence=0.60, timeframe=timeframe)
        self.smc = SMC()
        self.atr = ATR()
        self.risk_manager = RiskManager(min_risk_reward=settings.MIN_RISK_REWARD_RATIO)

    def analyze(self, candle_list: CandleList, regime: str = "trending") -> Optional[TradingSignal]:
        if not self._validate_candle_count(candle_list, 50):
            return None

        opens = candle_list.opens
        highs = candle_list.highs
        lows = candle_list.lows
        closes = candle_list.closes
        volumes = candle_list.volumes
        current_price = closes[-1]

        # Calculate SMC features
        smc_data = self.smc.calculate_from_ohlc(opens, highs, lows, closes, volumes)
        fvgs = smc_data.get("fvgs", [])
        order_blocks = smc_data.get("order_blocks", [])

        atr_values = self.atr.calculate_from_ohlc(highs, lows, closes)
        atr = atr_values[-1] if atr_values else current_price * 0.02

        # Filter recent active ones (last 20 candles)
        recent_index = len(closes) - 20
        active_fvgs = [f for f in fvgs if f["active"] and f["index"] >= recent_index]
        active_obs = [ob for ob in order_blocks if ob["active"] and ob["index"] >= recent_index]

        signal_type = None
        confidence = 0.0
        reasons = []

        # Find proximity to OBs and FVGs
        bullish_confluence = 0
        bearish_confluence = 0

        # Bullish Check
        for ob in active_obs:
            if ob["type"] == "bullish":
                if ob["bottom"] <= current_price <= ob["top"] + (atr * 0.5):
                    bullish_confluence += 0.5
                    reasons.append(f"Price inside/near Bullish Order Block (from candle -{len(closes)-ob['index']})")
                    break

        for fvg in active_fvgs:
            if fvg["type"] == "bullish":
                if fvg["bottom"] <= current_price <= fvg["top"] + (atr * 0.5):
                    bullish_confluence += 0.4
                    reasons.append(f"Price inside/near Bullish FVG (from candle -{len(closes)-fvg['index']})")
                    break

        # Bearish Check
        for ob in active_obs:
            if ob["type"] == "bearish":
                if ob["bottom"] - (atr * 0.5) <= current_price <= ob["top"]:
                    bearish_confluence += 0.5
                    reasons.append(f"Price inside/near Bearish Order Block (from candle -{len(closes)-ob['index']})")
                    break

        for fvg in active_fvgs:
            if fvg["type"] == "bearish":
                if fvg["bottom"] - (atr * 0.5) <= current_price <= fvg["top"]:
                    bearish_confluence += 0.4
                    reasons.append(f"Price inside/near Bearish FVG (from candle -{len(closes)-fvg['index']})")
                    break

        if bullish_confluence > bearish_confluence and bullish_confluence >= 0.4:
            signal_type = SignalType.BUY
            confidence = min(0.60 + bullish_confluence * 0.4, 0.95)
        elif bearish_confluence > bullish_confluence and bearish_confluence >= 0.4:
            signal_type = SignalType.SELL
            confidence = min(0.60 + bearish_confluence * 0.4, 0.95)

        if signal_type is None or confidence < self.min_confidence:
            return None

        direction = "long" if signal_type == SignalType.BUY else "short"

        # Calculate TP/SL, passing SMC levels to risk manager to hide stop losses
        tp, sl, meta = self.risk_manager.calculate_adaptive_tp_sl(
            entry_price=current_price,
            atr=atr,
            direction=direction,
            regime=regime,
            smc_data=smc_data  # Pass SMC data
        )

        if signal_type == SignalType.BUY and (tp <= current_price or sl >= current_price):
            return None
        if signal_type == SignalType.SELL and (tp >= current_price or sl <= current_price):
            return None

        return self._create_signal(
            symbol=candle_list.symbol,
            signal_type=signal_type,
            entry_price=current_price,
            take_profit_price=tp,
            stop_loss_price=sl,
            confidence=confidence,
            indicators_used=["Order Blocks", "Fair Value Gaps", "ATR"],
            indicator_values={
                "bullish_confluence": round(bullish_confluence, 2),
                "bearish_confluence": round(bearish_confluence, 2),
                "reasons": reasons,
                "ATR": round(atr, 6),
                **meta,
            },
        )
