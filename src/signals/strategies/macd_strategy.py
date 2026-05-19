"""
MACD Trading Strategy — ATR-Adaptive Version

Buy on bullish crossover, Sell on bearish crossover.
TP and SL dynamically computed from ATR (no hardcoded percentages).
"""

from __future__ import annotations


from typing import Optional
from src.data.models import CandleList
from src.signals.signal import TradingSignal, SignalType
from src.signals.strategies.base import BaseStrategy
from src.indicators.macd import MACD
from src.indicators.atr import ATR
from src.indicators.fibonacci import FibonacciLevels
from src.risk.risk_manager import RiskManager
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


class MACDStrategy(BaseStrategy):
    """MACD-based trading strategy with ATR-adaptive TP/SL."""

    def __init__(self, timeframe: str = "15m"):
        super().__init__(name="MACD Strategy", min_confidence=0.65, timeframe=timeframe)
        self.macd = MACD()
        self.atr = ATR(period=14)
        self.fib = FibonacciLevels(swing_lookback=50)
        self.risk_manager = RiskManager(
            min_risk_reward=settings.MIN_RISK_REWARD_RATIO,
            risk_per_trade_percent=settings.RISK_PER_TRADE_PERCENT,
        )

    def analyze(self, candle_list: CandleList, regime: str = "trending") -> Optional[TradingSignal]:
        """
        Analyze using MACD indicator with ATR-adaptive TP/SL.

        Rules:
        - BUY: MACD line crosses above Signal line (bullish crossover)
        - SELL: MACD line crosses below Signal line (bearish crossover)
        - Confidence boosted when crossover happens below/above zero
        """
        if not self._validate_candle_count(candle_list, 50):
            return None

        current_price = candle_list.latest_close
        if current_price is None:
            return None

        closes = candle_list.closes
        highs = candle_list.highs
        lows = candle_list.lows

        # Calculate MACD
        histogram = self.macd.calculate(closes)
        if len(histogram) < 2:
            return None

        macd_vals = self.macd.get_macd_values()
        if not macd_vals or not macd_vals.get("histogram"):
            return None

        latest_histogram = macd_vals["histogram"][-1]
        latest_macd = macd_vals["macd_line"][-1]
        latest_signal = macd_vals["signal_line"][-1]

        # Calculate ATR
        atr_values = self.atr.calculate_from_ohlc(highs, lows, closes)
        atr = atr_values[-1] if atr_values else 0

        # Calculate Fibonacci levels
        fib_data = None
        try:
            fib_data = self.fib.calculate_from_ohlc(highs, lows, closes)
        except Exception:
            pass

        signal_type = None
        confidence = 0.0

        if self.macd.is_bullish_crossover():
            logger.info(f"MACD Buy signal for {candle_list.symbol}")
            signal_type = SignalType.BUY
            # Baseline confidence, boosted if histogram is positive and crossover below zero
            confidence = 0.65
            if latest_macd < 0:  # crossover in negative territory = stronger signal
                confidence += 0.10
            if abs(latest_histogram) > abs(macd_vals["histogram"][-2] if len(macd_vals["histogram"]) > 1 else 0):
                confidence += 0.05  # expanding histogram = momentum

        elif self.macd.is_bearish_crossover():
            logger.info(f"MACD Sell signal for {candle_list.symbol}")
            signal_type = SignalType.SELL
            confidence = 0.65
            if latest_macd > 0:  # crossover in positive territory = stronger signal
                confidence += 0.10
            if abs(latest_histogram) > abs(macd_vals["histogram"][-2] if len(macd_vals["histogram"]) > 1 else 0):
                confidence += 0.05

        if signal_type is None:
            return None

        confidence = min(confidence, 0.85)
        direction = "long" if signal_type == SignalType.BUY else "short"

        # Adaptive TP/SL
        tp, sl, meta = self.risk_manager.calculate_adaptive_tp_sl(
            entry_price=current_price,
            atr=atr if atr > 0 else current_price * 0.02,
            direction=direction,
            regime=regime,
            fib_levels=fib_data,
        )

        # Validate direction
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
            indicators_used=["MACD", "ATR"],
            indicator_values={
                "MACD": round(latest_macd, 6),
                "Signal": round(latest_signal, 6),
                "Histogram": round(latest_histogram, 6),
                "ATR": round(atr, 6),
                "regime": regime,
                **meta,
            },
        )
