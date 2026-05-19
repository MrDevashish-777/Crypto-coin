"""
Trading Signal Object and Response Models
"""

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional, List, Union, Any, Literal, Dict
from datetime import datetime


class SignalType(str, Enum):
    """Types of trading signals"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE = "close"


class SignalStrength(str, Enum):
    """Signal confidence/strength levels"""
    VERY_WEAK = "very_weak"
    WEAK = "weak"
    NEUTRAL = "neutral"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


@dataclass
class TargetLevel:
    """Target price level with optional metadata"""
    price: float
    percent_from_entry: float
    label: str = ""


@dataclass
class TradingSignal:
    """
    Comprehensive trading signal with entry, targets, and stop loss
    """
    symbol: str
    timeframe: str
    signal_type: SignalType
    entry_price: float
    take_profit: TargetLevel
    stop_loss: TargetLevel
    position_size: float  # As percentage of portfolio
    confidence: float  # 0.0 to 1.0
    strength: SignalStrength
    
    # Additional information
    timestamp: int  # Unix timestamp in ms
    generated_at: str  # ISO 8601 datetime string
    
    # Indicator-based information
    indicators_used: list  # List of indicators that generated the signal
    indicator_values: dict = None  # Dict of indicator values at time of signal
    
    # LLM analysis information
    llm_confidence: Optional[float] = None
    llm_sentiment: Optional[str] = None
    llm_analysis: Optional[str] = None
    
    # Metadata
    strategy_name: str = ""
    version: str = "1.0"
    tags: list = None

    def __post_init__(self):
        """Validate signal data"""
        if not (0 <= self.confidence <= 1):
            raise ValueError("Confidence must be between 0 and 1")
        if self.signal_type == SignalType.BUY:
            assert self.take_profit.price > self.entry_price, "TP must be above entry for BUY"
            assert self.stop_loss.price < self.entry_price, "SL must be below entry for BUY"
        elif self.signal_type == SignalType.SELL:
            assert self.take_profit.price < self.entry_price, "TP must be below entry for SELL"
            assert self.stop_loss.price > self.entry_price, "SL must be above entry for SELL"

        if self.tags is None:
            self.tags = []
        if self.indicator_values is None:
            self.indicator_values = {}

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        signal_dict = asdict(self)
        signal_dict['signal_type'] = self.signal_type.value
        signal_dict['strength'] = self.strength.value
        signal_dict['take_profit'] = asdict(self.take_profit)
        signal_dict['stop_loss'] = asdict(self.stop_loss)
        return signal_dict

    @property
    def risk_reward_ratio(self) -> float:
        """Calculate risk/reward ratio"""
        profit = abs(self.take_profit.price - self.entry_price)
        loss = abs(self.entry_price - self.stop_loss.price)
        return profit / loss if loss > 0 else 0

    @property
    def is_valid(self) -> bool:
        """Check if signal is valid"""
        return (
            self.confidence >= 0.5 and
            self.risk_reward_ratio >= 1.0 and
            self.position_size > 0
        )


@dataclass
class SignalResponse:
    """Standard API response for signals"""
    success: bool
    data: Any = None
    message: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()


def format_planitt_payload(
    *,
    asset: str,
    signal_type: Union[Literal["BUY", "SELL"], str],
    entry_range: List[float],
    stop_loss: float,
    take_profit: Dict[str, float],
    risk_reward_ratio: str,
    confidence: int,
    timeframe: str,
    strategy: str,
    reason: str,
    validity: str,
    created_at: datetime,
    status: Literal["active", "hit_tp", "hit_sl", "expired"] = "active",
    expires_at: Optional[datetime] = None,
    dedup_key: Optional[str] = None,
) -> dict:
    """
    Format a strict Planitt signal payload for the backend.

    The processor will still validate this payload against the strict Pydantic schema,
    but having this helper keeps the serialization contract consistent.
    """

    return {
        "asset": asset,
        "signal_type": str(signal_type).upper(),
        "entry_range": entry_range,
        "stop_loss": stop_loss,
        "take_profit": {
            "tp1": take_profit["tp1"],
            "tp2": take_profit["tp2"],
            "tp3": take_profit["tp3"],
        },
        "timeframe": timeframe,
        "confidence": confidence,
        "strategy": strategy,
        "reason": reason,
        "validity": validity,
        "created_at": created_at.isoformat(),
        "status": status,
        "risk_reward_ratio": risk_reward_ratio,
        # Optional internal fields
        "expires_at": expires_at.isoformat() if expires_at else None,
        "dedup_key": dedup_key,
    }
