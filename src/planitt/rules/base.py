from dataclasses import dataclass, field
from typing import Optional, Literal, Protocol

from src.data.models import CandleList
from src.signals.market_regime import RegimeResult
from src.indicators.nadaraya_watson import NWESnapshot

SignalSide = Literal["BUY", "SELL"]
SetupType = Literal[
    "trend_pullback",
    "volume_breakout",
    "support_resistance_reversal",
    "fvg_ob_retest",
    "liquidity_sweep",
    "vwap_reclaim",
]

@dataclass
class RuleContext:
    candle_list: CandleList
    adx_trend_threshold: float = 25.0
    volume_multiplier: float = 1.5
    touch_tolerance_pct: float = 0.0025
    min_confluence_hits: int = 3
    
    # Computed State built by rules sequentially
    regime_result: Optional[RegimeResult] = None
    regime_tag: Optional[str] = None
    side: Optional[SignalSide] = None
    side_hits: tuple[str, ...] = ()
    
    ema20: Optional[float] = None
    ema50: Optional[float] = None
    ema200: Optional[float] = None
    
    rsi: Optional[float] = None
    prev_rsi: Optional[float] = None
    macd_hist: Optional[float] = None
    macd_hist_prev: Optional[float] = None
    
    atr: Optional[float] = None
    volume_ratio: Optional[float] = None
    current_volume: Optional[float] = None
    price: Optional[float] = None
    
    nwe_snap: Optional[NWESnapshot] = None
    
    swing_ok: bool = False
    
    key_level: Optional[float] = None
    breakout_level: Optional[float] = None
    setup_type: Optional[SetupType] = None
    
    confluence_hits: list[str] = field(default_factory=list)
    
    pattern_name: Optional[str] = None
    pattern_bias: Optional[Literal["bull", "bear"]] = None
    pattern_strength: float = 0.0
    pattern_confirmed: bool = False
    
    agreeing_sources: int = 0
    pre_confidence: float = 0.0
    vote_hits: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RuleResult:
    passed: bool
    reason: Optional[str] = None
    
    @classmethod
    def ok(cls) -> "RuleResult":
        return cls(passed=True)
        
    @classmethod
    def reject(cls, reason: str) -> "RuleResult":
        return cls(passed=False, reason=reason)


class ConfluenceRule(Protocol):
    def evaluate(self, context: RuleContext) -> RuleResult:
        ...
