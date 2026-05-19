"""
Base Strategy Class
Abstract base for all trading strategies
"""

from abc import ABC, abstractmethod
from typing import Optional
from src.data.models import CandleList
from src.signals.signal import TradingSignal, SignalType, SignalStrength
from src.indicators.base import BaseIndicator
import logging

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies"""

    def __init__(
        self,
        name: str,
        min_confidence: float = 0.60,
        timeframe: str = "15m",
    ):
        """
        Initialize strategy
        
        Args:
            name: Strategy name
            min_confidence: Minimum confidence threshold (0-1)
            timeframe: Default timeframe
        """
        self.name = name
        self.min_confidence = min_confidence
        self.timeframe = timeframe
        self.indicators = {}

    @abstractmethod
    def analyze(self, candle_list: CandleList) -> Optional[TradingSignal]:
        """
        Analyze candledata and generate trading signal
        
        Args:
            candle_list: CandleList object with OHLCV data
        
        Returns:
            TradingSignal if signal is generated, None otherwise
        """
        pass

    def _validate_candle_count(self, candle_list: CandleList, min_count: int = 50) -> bool:
        """Validate if we have enough candles"""
        if len(candle_list) < min_count:
            logger.warning(
                f"Insufficient candles for {self.name}: {len(candle_list)} < {min_count}"
            )
            return False
        return True

    def _get_signal_strength(self, confidence: float) -> SignalStrength:
        """Convert confidence to signal strength"""
        if confidence >= 0.9:
            return SignalStrength.VERY_STRONG
        elif confidence >= 0.75:
            return SignalStrength.STRONG
        elif confidence >= 0.5:
            return SignalStrength.NEUTRAL
        elif confidence >= 0.3:
            return SignalStrength.WEAK
        else:
            return SignalStrength.VERY_WEAK

    def _create_signal(
        self,
        symbol: str,
        signal_type: SignalType,
        entry_price: float,
        take_profit_price: float,
        stop_loss_price: float,
        confidence: float,
        indicators_used: list,
        indicator_values: dict = None,
        llm_confidence: float = None,
        llm_sentiment: str = None,
        llm_analysis: str = None,
    ) -> TradingSignal:
        """Create a trading signal"""
        from datetime import datetime
        from src.utils.helpers import get_timestamp_ms

        strength = self._get_signal_strength(confidence)

        # Calculate TP and SL percentages
        if signal_type == SignalType.BUY:
            tp_pct = ((take_profit_price - entry_price) / entry_price) * 100
            sl_pct = ((entry_price - stop_loss_price) / entry_price) * 100
        else:
            tp_pct = ((entry_price - take_profit_price) / entry_price) * 100
            sl_pct = ((stop_loss_price - entry_price) / entry_price) * 100

        from src.signals.signal import TargetLevel

        signal = TradingSignal(
            symbol=symbol,
            timeframe=self.timeframe,
            signal_type=signal_type,
            entry_price=entry_price,
            take_profit=TargetLevel(
                price=take_profit_price,
                percent_from_entry=tp_pct,
                label="Take Profit"
            ),
            stop_loss=TargetLevel(
                price=stop_loss_price,
                percent_from_entry=sl_pct,
                label="Stop Loss"
            ),
            position_size=2.0,  # Default 2% of portfolio
            confidence=confidence,
            strength=strength,
            timestamp=get_timestamp_ms(),
            generated_at=datetime.utcnow().isoformat(),
            indicators_used=indicators_used,
            indicator_values=indicator_values or {},
            strategy_name=self.name,
            llm_confidence=llm_confidence,
            llm_sentiment=llm_sentiment,
            llm_analysis=llm_analysis,
        )

        return signal
