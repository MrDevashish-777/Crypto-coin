"""
Stochastic + RSI Strategy (StochRSI hybrid)

Combines Stochastic Oscillator and RSI for stronger mean-reversion signals.
Best used in RANGING markets.

BUY:  Stochastic K crosses above D in oversold zone (<20) + RSI also oversold (<35)
SELL: Stochastic K crosses below D in overbought zone (>80) + RSI also overbought (>65)

Double confirmation from two oscillators dramatically improves signal quality.
"""

from __future__ import annotations


from typing import Optional
from src.data.models import CandleList
from src.signals.signal import TradingSignal, SignalType
from src.signals.strategies.base import BaseStrategy
from src.indicators.stochastic import Stochastic
from src.indicators.rsi import RSI
from src.indicators.atr import ATR
from src.indicators.williams_r import WilliamsR
from src.risk.risk_manager import RiskManager
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


class StochasticRSIStrategy(BaseStrategy):
    """Stochastic + RSI confluence strategy for ranging markets."""

    def __init__(self, timeframe: str = "15m"):
        super().__init__(name="Stochastic RSI Strategy", min_confidence=0.65, timeframe=timeframe)
        self.stoch = Stochastic(k_period=14, d_period=3, overbought=80, oversold=20)
        self.rsi = RSI(period=14)
        self.williams_r = WilliamsR(period=14)
        self.atr = ATR(period=14)
        self.risk_manager = RiskManager(min_risk_reward=settings.MIN_RISK_REWARD_RATIO)

    def analyze(self, candle_list: CandleList, regime: str = "ranging") -> Optional[TradingSignal]:
        """
        Generate signals when Stochastic and RSI both confirm a reversal.
        Williams %R adds a third confirmation layer.
        """
        if not self._validate_candle_count(candle_list, 50):
            return None

        closes = candle_list.closes
        highs = candle_list.highs
        lows = candle_list.lows
        current_price = closes[-1]

        self.stoch.calculate_from_ohlc(highs, lows, closes)
        self.rsi.calculate(closes)
        self.williams_r.calculate_from_ohlc(highs, lows, closes)
        atr_values = self.atr.calculate_from_ohlc(highs, lows, closes)

        if not self.rsi.is_ready() or not atr_values:
            return None

        stoch_vals = self.stoch.get_values()
        k = stoch_vals.get("K")
        d = stoch_vals.get("D")
        rsi_val = self.rsi.latest_value
        atr = atr_values[-1]

        if k is None or d is None:
            return None

        wr_scores = self.williams_r.get_signal_score()

        signal_type = None
        confidence = 0.0

        # BUY: Stoch K crosses above D from oversold + RSI oversold
        if self.stoch.is_k_crossing_above_d() and self.stoch.is_oversold() and rsi_val < 40:
            signal_type = SignalType.BUY
            confidence = 0.65
            # Extra from Williams %R oversold
            confidence += wr_scores.get("bull_score", 0) * 0.15
            # Deeper oversold = stronger signal
            oversold_depth = max(0, 30 - rsi_val) / 30
            confidence += oversold_depth * 0.10

        # SELL: Stoch K crosses below D from overbought + RSI overbought
        elif not self.stoch.is_k_crossing_above_d() and self.stoch.is_overbought() and rsi_val > 60:
            # Check K was previously above D and now below
            k_val = self.stoch.k_line
            d_val = self.stoch.d_line
            active_k = [v for v in k_val if v is not None]
            active_d = [v for v in d_val if v is not None]
            if len(active_k) >= 2 and len(active_d) >= 2:
                if active_k[-2] >= active_d[-2] and active_k[-1] < active_d[-1]:
                    signal_type = SignalType.SELL
                    confidence = 0.65
                    confidence += wr_scores.get("bear_score", 0) * 0.15
                    overbought_height = max(0, rsi_val - 70) / 30
                    confidence += overbought_height * 0.10

        if signal_type is None:
            return None

        direction = "long" if signal_type == SignalType.BUY else "short"
        # Ranging: use tighter TP/SL
        tp, sl, meta = self.risk_manager.calculate_adaptive_tp_sl(
            entry_price=current_price,
            atr=atr,
            direction=direction,
            regime="ranging",
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
            confidence=min(confidence, 0.88),
            indicators_used=["Stochastic", "RSI", "WilliamsR", "ATR"],
            indicator_values={
                "Stoch_K": round(k, 2),
                "Stoch_D": round(d, 2),
                "RSI": round(rsi_val, 2),
                "Williams_R": round(self.williams_r.get_current_value() or -50, 2),
                **meta,
            },
        )
