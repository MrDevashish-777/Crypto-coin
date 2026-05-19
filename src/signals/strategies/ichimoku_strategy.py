"""
Ichimoku Strategy

Full Ichimoku Cloud system entry logic:

BUY conditions (in order of importance):
1. Price is above the Kumo (cloud) - primary trend filter
2. Tenkan-sen crosses above Kijun-sen (TK cross) - entry signal
3. Kumo is bullish (Senkou A > Senkou B) - cloud confirmation
4. Chikou span is above price 26 periods ago - lagging confirmation

SL: Below Kijun-sen (base line support)
TP: Fibonacci level or ATR-based target
"""

from __future__ import annotations


from typing import Optional
from src.data.models import CandleList
from src.signals.signal import TradingSignal, SignalType
from src.signals.strategies.base import BaseStrategy
from src.indicators.ichimoku import Ichimoku
from src.indicators.atr import ATR
from src.indicators.fibonacci import FibonacciLevels
from src.risk.risk_manager import RiskManager
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


class IchimokuStrategy(BaseStrategy):
    """Full Ichimoku Cloud trading strategy."""

    def __init__(self, timeframe: str = "4h"):
        super().__init__(name="Ichimoku Strategy", min_confidence=0.70, timeframe=timeframe)
        self.ichimoku = Ichimoku(tenkan_period=9, kijun_period=26, senkou_b_period=52)
        self.atr = ATR(period=14)
        self.fib = FibonacciLevels(swing_lookback=52)
        self.risk_manager = RiskManager(min_risk_reward=settings.MIN_RISK_REWARD_RATIO)

    def analyze(self, candle_list: CandleList, regime: str = "trending") -> Optional[TradingSignal]:
        """Use Ichimoku cloud for high-conviction trend entries."""
        if not self._validate_candle_count(candle_list, 100):
            return None

        closes = candle_list.closes
        highs = candle_list.highs
        lows = candle_list.lows
        current_price = closes[-1]

        self.ichimoku.calculate_from_ohlc(highs, lows, closes)
        atr_values = self.atr.calculate_from_ohlc(highs, lows, closes)
        atr = atr_values[-1] if atr_values else 0

        fib_data = None
        try:
            fib_data = self.fib.calculate_from_ohlc(highs, lows, closes)
        except Exception:
            pass

        bull_strength = self.ichimoku.bullish_signal_strength(current_price)
        bear_strength = self.ichimoku.bearish_signal_strength(current_price)

        ichi_current = self.ichimoku.get_current()
        kijun = ichi_current.get("kijun")

        signal_type = None
        confidence = 0.0

        # BUY: strong bullish conditions with TK cross
        if bull_strength >= 0.60 and self.ichimoku.bullish_tk_cross():
            signal_type = SignalType.BUY
            confidence = 0.65 + bull_strength * 0.25

        # SELL: strong bearish conditions with TK cross
        elif bear_strength >= 0.60 and self.ichimoku.bearish_tk_cross():
            signal_type = SignalType.SELL
            confidence = 0.65 + bear_strength * 0.25

        if signal_type is None:
            return None

        direction = "long" if signal_type == SignalType.BUY else "short"

        # Use Kijun-sen as SL anchor (strong support/resistance)
        if kijun and direction == "long" and kijun < current_price:
            sl_anchor = kijun - (atr * 0.3)  # small buffer below kijun
        elif kijun and direction == "short" and kijun > current_price:
            sl_anchor = kijun + (atr * 0.3)
        else:
            sl_anchor = None

        if sl_anchor:
            risk = abs(current_price - sl_anchor)
            tp_distance = risk * max(settings.MIN_RISK_REWARD_RATIO + 0.5, 2.0)
            if direction == "long":
                tp = current_price + tp_distance
                sl = sl_anchor
            else:
                tp = current_price - tp_distance
                sl = sl_anchor

            # Try Fibonacci snap for TP
            if fib_data and fib_data.get("extensions"):
                fib_tp1 = self.fib.get_fib_tp1()
                if fib_tp1:
                    if direction == "long" and fib_tp1 > current_price:
                        tp = max(tp, fib_tp1)
                    elif direction == "short" and fib_tp1 < current_price:
                        tp = min(tp, fib_tp1)
        else:
            tp, sl, _ = self.risk_manager.calculate_adaptive_tp_sl(
                entry_price=current_price, atr=atr, direction=direction, regime=regime,
                fib_levels=fib_data
            )

        if signal_type == SignalType.BUY and (tp <= current_price or sl >= current_price):
            return None
        if signal_type == SignalType.SELL and (tp >= current_price or sl <= current_price):
            return None

        cloud_sr = self.ichimoku.get_cloud_support_resistance()
        return self._create_signal(
            symbol=candle_list.symbol,
            signal_type=signal_type,
            entry_price=current_price,
            take_profit_price=tp,
            stop_loss_price=sl,
            confidence=min(confidence, 0.92),
            indicators_used=["Ichimoku", "ATR", "Fibonacci"],
            indicator_values={
                "Tenkan": round(ichi_current.get("tenkan") or 0, 4),
                "Kijun": round(kijun or 0, 4),
                "Cloud_Bullish": self.ichimoku.is_cloud_bullish(),
                "Above_Cloud": self.ichimoku.is_price_above_cloud(current_price),
                "Bull_Strength": round(bull_strength, 3),
                "Bear_Strength": round(bear_strength, 3),
                "Cloud_Support": cloud_sr[0],
                "Cloud_Resistance": cloud_sr[1],
            },
        )
