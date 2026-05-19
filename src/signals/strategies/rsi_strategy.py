"""
RSI Trading Strategy — ATR-Adaptive Version

Buy when RSI crosses above oversold, Sell when it crosses below overbought.
TP and SL are computed dynamically using ATR (no hardcoded percentages).
Market regime is considered for multiplier selection.
"""

from __future__ import annotations


from typing import Optional
from src.data.models import CandleList
from src.signals.signal import TradingSignal, SignalType
from src.signals.strategies.base import BaseStrategy
from src.indicators.rsi import RSI
from src.indicators.atr import ATR
from src.indicators.fibonacci import FibonacciLevels
from src.risk.risk_manager import RiskManager
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


class RSIStrategy(BaseStrategy):
    """RSI-based trading strategy with ATR-adaptive TP/SL."""

    def __init__(self, timeframe: str = "15m"):
        super().__init__(name="RSI Strategy", min_confidence=0.60, timeframe=timeframe)
        self.rsi = RSI(period=14)
        self.atr = ATR(period=14)
        self.fib = FibonacciLevels(swing_lookback=50)
        self.risk_manager = RiskManager(
            min_risk_reward=settings.MIN_RISK_REWARD_RATIO,
            risk_per_trade_percent=settings.RISK_PER_TRADE_PERCENT,
        )

    def analyze(self, candle_list: CandleList, regime: str = "trending") -> Optional[TradingSignal]:
        """
        Analyze using RSI indicator with ATR-adaptive TP/SL.

        Args:
            candle_list: CandleList with OHLCV data
            regime: Market regime string ('trending', 'ranging', 'volatile')

        Rules:
        - BUY: RSI crosses above 30 (oversold recovery)
        - SELL: RSI crosses below 70 (overbought rejection)
        - TP/SL: ATR-based, scaled to market regime
        """
        if not self._validate_candle_count(candle_list, 50):
            return None

        current_price = candle_list.latest_close
        if current_price is None:
            return None

        closes = candle_list.closes
        highs = candle_list.highs
        lows = candle_list.lows

        # Calculate RSI
        self.rsi.calculate(closes)
        if not self.rsi.is_ready():
            return None

        # Calculate ATR
        atr_values = self.atr.calculate_from_ohlc(highs, lows, closes)
        atr = atr_values[-1] if atr_values else 0

        # Calculate Fibonacci levels for level snapping
        fib_data = None
        try:
            fib_data = self.fib.calculate_from_ohlc(highs, lows, closes)
        except Exception:
            pass

        signal_type = None
        confidence = 0.0

        # BUY Signal: RSI crosses above oversold (30)
        if self.rsi.is_crossing_above_oversold():
            logger.info(f"RSI Buy signal for {candle_list.symbol} — RSI: {self.rsi.latest_value:.1f}")
            signal_type = SignalType.BUY
            # Confidence scales with how deep RSI was oversold
            rsi_depth = max(0, 30 - (self.rsi.previous_value or 30))
            confidence = min(0.80, 0.55 + (rsi_depth / 30) * 0.25)

        # SELL Signal: RSI crosses below overbought (70)
        elif self.rsi.is_crossing_below_overbought():
            logger.info(f"RSI Sell signal for {candle_list.symbol} — RSI: {self.rsi.latest_value:.1f}")
            signal_type = SignalType.SELL
            rsi_height = max(0, (self.rsi.previous_value or 70) - 70)
            confidence = min(0.80, 0.55 + (rsi_height / 30) * 0.25)

        if signal_type is None:
            return None

        direction = "long" if signal_type == SignalType.BUY else "short"

        # Calculate adaptive TP/SL
        tp, sl, meta = self.risk_manager.calculate_adaptive_tp_sl(
            entry_price=current_price,
            atr=atr if atr > 0 else current_price * 0.02,
            direction=direction,
            regime=regime,
            fib_levels=fib_data,
        )

        # Validate TP/SL direction
        if signal_type == SignalType.BUY:
            if tp <= current_price or sl >= current_price:
                logger.warning(f"RSI BUY: invalid TP/SL for {candle_list.symbol}, skipping")
                return None
        else:
            if tp >= current_price or sl <= current_price:
                logger.warning(f"RSI SELL: invalid TP/SL for {candle_list.symbol}, skipping")
                return None

        return self._create_signal(
            symbol=candle_list.symbol,
            signal_type=signal_type,
            entry_price=current_price,
            take_profit_price=tp,
            stop_loss_price=sl,
            confidence=confidence,
            indicators_used=["RSI", "ATR"],
            indicator_values={
                "RSI": round(self.rsi.latest_value, 2),
                "ATR": round(atr, 6),
                "regime": regime,
                **meta,
            },
        )
