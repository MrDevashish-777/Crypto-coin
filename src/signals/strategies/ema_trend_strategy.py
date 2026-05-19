"""
EMA Trend-Follow Strategy

Uses multi-EMA stack alignment for trend-following entries.
Entry is on pullbacks to the EMA21 in the direction of the larger trend.

EMA periods: 9, 21, 50, 200

Full bullish stack:  EMA9 > EMA21 > EMA50 > EMA200
Full bearish stack: EMA9 < EMA21 < EMA50 < EMA200

Pullback entry: Price touches EMA21 after a stack is confirmed.
"""

from __future__ import annotations


from typing import Optional, List
from src.data.models import CandleList
from src.signals.signal import TradingSignal, SignalType
from src.signals.strategies.base import BaseStrategy
from src.indicators.ema import EMA
from src.indicators.atr import ATR
from src.indicators.rsi import RSI
from src.risk.risk_manager import RiskManager
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


class EMATrendStrategy(BaseStrategy):
    """Multi-EMA stack trend-following strategy with pullback entries."""

    def __init__(self, timeframe: str = "1h"):
        super().__init__(name="EMA Trend Strategy", min_confidence=0.65, timeframe=timeframe)
        self.ema9 = EMA(period=9)
        self.ema21 = EMA(period=21)
        self.ema50 = EMA(period=50)
        self.ema200 = EMA(period=200)
        self.atr = ATR(period=14)
        self.rsi = RSI(period=14)
        self.risk_manager = RiskManager(min_risk_reward=settings.MIN_RISK_REWARD_RATIO)

    def analyze(self, candle_list: CandleList, regime: str = "trending") -> Optional[TradingSignal]:
        """
        Detect EMA stack alignment and pullback entry.

        BUY: Full bullish stack + price pulls back to EMA21 + RSI 40-60 (not extended)
        SELL: Full bearish stack + price bounces to EMA21 + RSI 40-60
        """
        if not self._validate_candle_count(candle_list, 210):
            return None

        closes = candle_list.closes
        highs = candle_list.highs
        lows = candle_list.lows
        current_price = closes[-1]

        self.ema9.calculate(closes)
        self.ema21.calculate(closes)
        self.ema50.calculate(closes)
        self.ema200.calculate(closes)
        self.rsi.calculate(closes)
        atr_values = self.atr.calculate_from_ohlc(highs, lows, closes)

        e9 = self.ema9.latest_value
        e21 = self.ema21.latest_value
        e50 = self.ema50.latest_value
        e200 = self.ema200.latest_value
        rsi_val = self.rsi.latest_value
        atr = atr_values[-1] if atr_values else 0

        if any(v is None for v in [e9, e21, e50, e200, rsi_val]):
            return None

        # Define stack conditions
        full_bull_stack = e9 > e21 > e50 > e200
        full_bear_stack = e9 < e21 < e50 < e200

        # Partial bull: at minimum EMA21 > EMA50 > EMA200 (more common)
        partial_bull = e21 > e50 > e200
        partial_bear = e21 < e50 < e200

        signal_type = None
        confidence = 0.0

        # EMA21 zone: within 0.5% of EMA21 = pullback zone
        ema21_zone = abs(current_price - e21) / e21 < 0.005
        # Also count: recently touched EMA21 (within last 2 bars)
        prev_close = closes[-2] if len(closes) >= 2 else current_price
        prev_touched = abs(prev_close - e21) / e21 < 0.008

        # BUY: bull stack + pullback to EMA21 + RSI not overbought
        if (full_bull_stack or partial_bull) and (ema21_zone or prev_touched) and 35 < rsi_val < 65:
            signal_type = SignalType.BUY
            confidence = 0.70 if full_bull_stack else 0.63
            # Extra boost if bouncing off EMA21 with momentum
            if current_price > e9 and rsi_val > 50:
                confidence += 0.08
            if e50 > e200:  # Long-term bull market
                confidence += 0.07

        # SELL: bear stack + bounce to EMA21 + RSI not oversold
        elif (full_bear_stack or partial_bear) and (ema21_zone or prev_touched) and 35 < rsi_val < 65:
            signal_type = SignalType.SELL
            confidence = 0.70 if full_bear_stack else 0.63
            if current_price < e9 and rsi_val < 50:
                confidence += 0.08
            if e50 < e200:  # Long-term bear market
                confidence += 0.07

        if signal_type is None:
            return None

        direction = "long" if signal_type == SignalType.BUY else "short"
        tp, sl, meta = self.risk_manager.calculate_adaptive_tp_sl(
            entry_price=current_price,
            atr=atr if atr > 0 else current_price * 0.015,
            direction=direction,
            regime=regime,
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
            confidence=min(confidence, 0.92),
            indicators_used=["EMA9", "EMA21", "EMA50", "EMA200", "RSI", "ATR"],
            indicator_values={
                "EMA9": round(e9, 4), "EMA21": round(e21, 4),
                "EMA50": round(e50, 4), "EMA200": round(e200, 4),
                "RSI": round(rsi_val, 2), "ATR": round(atr, 6),
                "Full_Stack": full_bull_stack or full_bear_stack,
                **meta,
            },
        )
