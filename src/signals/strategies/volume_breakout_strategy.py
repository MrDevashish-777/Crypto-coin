"""
Volume Breakout Strategy

Detects when price breaks above a key resistance level with significantly
above-average volume — one of the most reliable crypto trading patterns.

Conditions:
1. Price breaks above the 20-bar high (resistance breakout)
2. Volume is >= 1.8x the 20-period average volume
3. OBV is trending up (smart money confirms)
4. RSI is in bullish territory (not overbought)

For short: Price breaks below 20-bar low, high volume, OBV falling.
"""

from __future__ import annotations


from typing import Optional
from src.data.models import CandleList
from src.signals.signal import TradingSignal, SignalType
from src.signals.strategies.base import BaseStrategy
from src.indicators.atr import ATR
from src.indicators.rsi import RSI
from src.indicators.obv import OBV
from src.risk.risk_manager import RiskManager
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


class VolumeBreakoutStrategy(BaseStrategy):
    """Volume-confirmed price breakout strategy."""

    def __init__(
        self,
        timeframe: str = "1h",
        lookback: int = 20,
        volume_multiplier: float = 1.8,
    ):
        super().__init__(name="Volume Breakout", min_confidence=0.68, timeframe=timeframe)
        self.lookback = lookback
        self.volume_multiplier = volume_multiplier
        self.atr = ATR(period=14)
        self.rsi = RSI(period=14)
        self.obv = OBV()
        self.risk_manager = RiskManager(min_risk_reward=settings.MIN_RISK_REWARD_RATIO)

    def analyze(self, candle_list: CandleList, regime: str = "trending") -> Optional[TradingSignal]:
        """Detect volume-confirmed breakouts."""
        if not self._validate_candle_count(candle_list, self.lookback + 10):
            return None

        closes = candle_list.closes
        highs = candle_list.highs
        lows = candle_list.lows
        volumes = candle_list.volumes
        current_price = closes[-1]

        self.rsi.calculate(closes)
        self.obv.calculate_from_cv(closes, volumes)
        atr_values = self.atr.calculate_from_ohlc(highs, lows, closes)

        if not self.rsi.is_ready() or not atr_values:
            return None

        atr = atr_values[-1]
        rsi_val = self.rsi.latest_value

        # Previous N-period high/low (exclude current candle)
        prev_highs = highs[-(self.lookback + 1):-1]
        prev_lows = lows[-(self.lookback + 1):-1]
        period_high = max(prev_highs) if prev_highs else current_price
        period_low = min(prev_lows) if prev_lows else current_price

        # Volume confirmation
        prev_volumes = volumes[-(self.lookback + 1):-1]
        avg_volume = sum(prev_volumes) / len(prev_volumes) if prev_volumes else 0
        current_volume = volumes[-1]
        volume_surge = current_volume >= avg_volume * self.volume_multiplier
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        # OBV confirmation
        obv_up = self.obv.is_rising(lookback=3)
        obv_down = self.obv.is_falling(lookback=3)

        signal_type = None
        confidence = 0.0

        # BULLISH BREAKOUT: price closes above prior N-period high with volume
        if current_price > period_high and volume_surge and rsi_val < 75:
            signal_type = SignalType.BUY
            confidence = 0.68
            if obv_up:
                confidence += 0.10
            if volume_ratio >= 2.5:  # Very strong surge
                confidence += 0.08
            if rsi_val > 50:
                confidence += 0.05
            if regime in ("trending_up", "trending"):
                confidence += 0.07

        # BEARISH BREAKDOWN: price closes below prior N-period low with volume
        elif current_price < period_low and volume_surge and rsi_val > 25:
            signal_type = SignalType.SELL
            confidence = 0.68
            if obv_down:
                confidence += 0.10
            if volume_ratio >= 2.5:
                confidence += 0.08
            if rsi_val < 50:
                confidence += 0.05
            if regime in ("trending_down", "trending"):
                confidence += 0.07

        if signal_type is None:
            return None

        direction = "long" if signal_type == SignalType.BUY else "short"

        # For breakouts: use trending multipliers (wide TP — momentum trade)
        breakout_regime = "trending"
        tp, sl, meta = self.risk_manager.calculate_adaptive_tp_sl(
            entry_price=current_price,
            atr=atr,
            direction=direction,
            regime=breakout_regime,
        )

        # For breakout SL: slightly tighter — below the breakout candle low/high
        if direction == "long":
            candle_sl = lows[-1] - (atr * 0.3)
            sl = max(candle_sl, sl)  # Use tighter of the two
            if sl >= current_price:
                return None
        else:
            candle_sl = highs[-1] + (atr * 0.3)
            sl = min(candle_sl, sl)
            if sl <= current_price:
                return None

        if signal_type == SignalType.BUY and tp <= current_price:
            return None
        if signal_type == SignalType.SELL and tp >= current_price:
            return None

        return self._create_signal(
            symbol=candle_list.symbol,
            signal_type=signal_type,
            entry_price=current_price,
            take_profit_price=tp,
            stop_loss_price=sl,
            confidence=min(confidence, 0.92),
            indicators_used=["VolumeBreakout", "OBV", "RSI", "ATR"],
            indicator_values={
                "Period_High": round(period_high, 4),
                "Period_Low": round(period_low, 4),
                "Volume_Ratio": round(volume_ratio, 2),
                "Avg_Volume": round(avg_volume, 2),
                "OBV_Trending": obv_up if signal_type == SignalType.BUY else obv_down,
                "RSI": round(rsi_val, 2),
                "ATR": round(atr, 6),
            },
        )
