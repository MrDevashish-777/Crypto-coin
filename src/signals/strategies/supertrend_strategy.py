"""
Supertrend Strategy

Generates signals when the Supertrend indicator flips direction.
Confirmed with VWAP (institutional bias) and RSI (not extended).

The Supertrend line itself becomes the trailing stop loss.
"""

from __future__ import annotations


from typing import Optional
from src.data.models import CandleList
from src.signals.signal import TradingSignal, SignalType
from src.signals.strategies.base import BaseStrategy
from src.indicators.supertrend import Supertrend
from src.indicators.vwap import VWAP
from src.indicators.rsi import RSI
from src.indicators.atr import ATR
from src.risk.risk_manager import RiskManager
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


class SupertrendStrategy(BaseStrategy):
    """Supertrend flip strategy with VWAP bias and RSI filter."""

    def __init__(self, timeframe: str = "1h"):
        super().__init__(name="Supertrend Strategy", min_confidence=0.68, timeframe=timeframe)
        self.supertrend = Supertrend(atr_period=10, multiplier=3.0)
        self.vwap = VWAP()
        self.rsi = RSI(period=14)
        self.atr = ATR(period=14)
        self.risk_manager = RiskManager(min_risk_reward=settings.MIN_RISK_REWARD_RATIO)

    def analyze(self, candle_list: CandleList, regime: str = "trending") -> Optional[TradingSignal]:
        """
        Entry when Supertrend flips, confirmed by VWAP and RSI.

        BUY: Supertrend flips bullish + price above VWAP + RSI not overbought
        SELL: Supertrend flips bearish + price below VWAP + RSI not oversold

        SL = Supertrend line (dynamic trailing stop)
        TP = ATR × regime multiplier
        """
        if not self._validate_candle_count(candle_list, 50):
            return None

        closes = candle_list.closes
        highs = candle_list.highs
        lows = candle_list.lows
        volumes = candle_list.volumes
        current_price = closes[-1]

        self.supertrend.calculate_from_ohlc(highs, lows, closes)
        self.vwap.calculate_from_ohlcv(highs, lows, closes, volumes)
        self.rsi.calculate(closes)
        atr_values = self.atr.calculate_from_ohlc(highs, lows, closes)

        if not self.rsi.is_ready() or not atr_values:
            return None

        atr = atr_values[-1]
        rsi_val = self.rsi.latest_value
        st_current = self.supertrend.get_current()
        vwap_above = self.vwap.is_price_above_vwap(current_price)

        signal_type = None
        confidence = 0.0

        # BUY: Supertrend just turned bullish
        if self.supertrend.just_turned_bullish() and rsi_val < 70:
            signal_type = SignalType.BUY
            confidence = 0.68
            if vwap_above:
                confidence += 0.10
            if rsi_val > 50:  # Momentum confirming
                confidence += 0.05
            if regime in ("trending_up", "trending"):
                confidence += 0.07

        # SELL: Supertrend just turned bearish
        elif self.supertrend.just_turned_bearish() and rsi_val > 30:
            signal_type = SignalType.SELL
            confidence = 0.68
            if not vwap_above:
                confidence += 0.10
            if rsi_val < 50:
                confidence += 0.05
            if regime in ("trending_down", "trending"):
                confidence += 0.07

        if signal_type is None:
            return None

        direction = "long" if signal_type == SignalType.BUY else "short"

        # Use Supertrend line as the SL anchor
        dynamic_sl = self.supertrend.get_dynamic_stop_loss(direction)

        if dynamic_sl:
            # Validate and compute TP from risk manager using Supertrend SL
            risk = abs(current_price - dynamic_sl)
            tp_distance = risk * max(settings.MIN_RISK_REWARD_RATIO, 2.0)
            if direction == "long":
                tp = current_price + tp_distance
                sl = dynamic_sl
            else:
                tp = current_price - tp_distance
                sl = dynamic_sl
        else:
            tp, sl, _ = self.risk_manager.calculate_adaptive_tp_sl(
                entry_price=current_price, atr=atr, direction=direction, regime=regime
            )

        meta_dict = {
            "Supertrend": round(st_current.get("supertrend", 0) or 0, 4),
            "Trend": st_current.get("trend", 0),
            "VWAP_Above": vwap_above,
            "RSI": round(rsi_val, 2),
            "ATR": round(atr, 6),
        }

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
            confidence=min(confidence, 0.90),
            indicators_used=["Supertrend", "VWAP", "RSI", "ATR"],
            indicator_values=meta_dict,
        )
