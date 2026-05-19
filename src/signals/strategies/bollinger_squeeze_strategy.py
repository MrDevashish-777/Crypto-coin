"""
Bollinger Bands Squeeze Strategy

Logic:
1. Detect BB squeeze (bandwidth at low — market consolidating)
2. Wait for bands to expand (breakout beginning)
3. Confirm direction with RSI and OBV

This is one of the most powerful crypto patterns:
- Low volatility periods (squeeze) tend to precede explosive moves
- The squeeze itself doesn't tell direction — breakout candle + RSI + OBV does
"""

from __future__ import annotations


from typing import Optional
from src.data.models import CandleList
from src.signals.signal import TradingSignal, SignalType
from src.signals.strategies.base import BaseStrategy
from src.indicators.bollinger_bands import BollingerBands
from src.indicators.rsi import RSI
from src.indicators.atr import ATR
from src.indicators.obv import OBV
from src.risk.risk_manager import RiskManager
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


class BollingerSqueezeStrategy(BaseStrategy):
    """Bollinger Squeeze breakout strategy with volume confirmation."""

    def __init__(self, timeframe: str = "15m"):
        super().__init__(name="Bollinger Squeeze", min_confidence=0.65, timeframe=timeframe)
        self.bb = BollingerBands(period=20, std_devs=2.0)
        self.rsi = RSI(period=14)
        self.atr = ATR(period=14)
        self.obv = OBV()
        self.risk_manager = RiskManager(min_risk_reward=settings.MIN_RISK_REWARD_RATIO)

    def analyze(self, candle_list: CandleList, regime: str = "ranging") -> Optional[TradingSignal]:
        """Detect squeeze + breakout with RSI and OBV confirmation."""
        if not self._validate_candle_count(candle_list, 60):
            return None

        closes = candle_list.closes
        highs = candle_list.highs
        lows = candle_list.lows
        volumes = candle_list.volumes

        self.bb.calculate(closes)
        self.rsi.calculate(closes)
        atr_values = self.atr.calculate_from_ohlc(highs, lows, closes)
        self.obv.calculate_from_cv(closes, volumes)

        if not self.rsi.is_ready() or not atr_values:
            return None

        current_price = closes[-1]
        atr = atr_values[-1]
        bands = self.bb.get_bands()
        bw = self.bb.bandwidth

        if not bands["upper"] or not bands["lower"] or len(bw) < 20:
            return None

        # Step 1: Was there a prior squeeze? (bandwidth below 50% of 20-period average)
        recent_bw = bw[-20:]
        avg_bw = sum(recent_bw) / len(recent_bw)
        prior_squeeze = min(bw[-5:-1]) < avg_bw * 0.5 if len(bw) >= 5 else False

        # Step 2: Is bandwidth now expanding?
        is_expanding = self.bb.is_expanding()

        if not (prior_squeeze and is_expanding):
            return None

        rsi_val = self.rsi.latest_value
        obv_rising = self.obv.is_rising(lookback=3)
        obv_falling = self.obv.is_falling(lookback=3)

        signal_type = None
        confidence = 0.0

        # Bullish breakout: price above upper band, RSI > 50, OBV rising
        if self.bb.is_at_upper_band(current_price, tolerance=0.003) and rsi_val > 50:
            signal_type = SignalType.BUY
            confidence = 0.65
            if obv_rising:
                confidence += 0.10
            if rsi_val > 55:
                confidence += 0.05

        # Bearish breakdown: price below lower band, RSI < 50, OBV falling
        elif self.bb.is_at_lower_band(current_price, tolerance=0.003) and rsi_val < 50:
            signal_type = SignalType.SELL
            confidence = 0.65
            if obv_falling:
                confidence += 0.10
            if rsi_val < 45:
                confidence += 0.05

        if signal_type is None:
            return None

        direction = "long" if signal_type == SignalType.BUY else "short"
        tp, sl, meta = self.risk_manager.calculate_adaptive_tp_sl(
            entry_price=current_price,
            atr=atr,
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
            confidence=min(confidence, 0.90),
            indicators_used=["BollingerBands", "RSI", "OBV", "ATR"],
            indicator_values={
                "BB_Upper": round(bands["upper"], 4),
                "BB_Lower": round(bands["lower"], 4),
                "BB_Bandwidth": round(bands["bandwidth"], 4),
                "RSI": round(rsi_val, 2),
                "OBV_Rising": obv_rising,
                "Prior_Squeeze": prior_squeeze,
                **meta,
            },
        )
