"""
Master Confluence Strategy

Aggregates ALL available strategies and indicators into a single
weighted scoring system. Only generates a signal when multiple
independent sources agree on the same direction.

Scoring system:
- Each indicator/strategy produces a directional vote (bull/bear) with a score 0-1
- Weighted average of all agreeing scores = final confidence
- Minimum 3 agreeing sources required
- Minimum R:R = 1.5 enforced

TP uses best Fibonacci extension level. SL uses nearest support.
"""

from __future__ import annotations


from typing import Optional, Dict, List, Tuple
from src.data.models import CandleList
from src.signals.signal import TradingSignal, SignalType
from src.signals.strategies.base import BaseStrategy
from src.indicators.rsi import RSI
from src.indicators.macd import MACD
from src.indicators.bollinger_bands import BollingerBands
from src.indicators.stochastic import Stochastic
from src.indicators.atr import ATR
from src.indicators.ema import EMA
from src.indicators.adx import ADX
from src.indicators.supertrend import Supertrend
from src.indicators.ichimoku import Ichimoku
from src.indicators.obv import OBV
from src.indicators.vwap import VWAP
from src.indicators.cci import CCI
from src.indicators.williams_r import WilliamsR
from src.indicators.heikin_ashi import HeikinAshi
from src.indicators.candlestick_patterns import detect_latest_candlestick_pattern
from src.indicators.fibonacci import FibonacciLevels
from src.indicators.pivot_points import PivotPoints
from src.risk.risk_manager import RiskManager
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

# Weights for each indicator/signal source
INDICATOR_WEIGHTS = {
    "supertrend":   0.18,
    "ema_stack":    0.16,
    "ichimoku":     0.16,
    "macd":         0.10,
    "rsi":          0.10,
    "volume_obv":   0.10,
    "bollinger":    0.08,
    "cci":          0.06,
    "williams_r":   0.06,
    "candlestick":  settings.PATTERN_WEIGHT,
}


class ConfluenceStrategy(BaseStrategy):
    """Master confluence engine combining all indicators into one robust signal."""

    def __init__(self, timeframe: str = "1h", min_sources: int = 3):
        super().__init__(name="Confluence Strategy", min_confidence=0.65, timeframe=timeframe)
        self.min_sources = min_sources

        # Indicators
        self.rsi = RSI(period=14)
        self.macd_ind = MACD()
        self.bb = BollingerBands(period=20)
        self.stoch = Stochastic(k_period=14, d_period=3)
        self.atr = ATR(period=14)
        self.ema9 = EMA(period=9)
        self.ema21 = EMA(period=21)
        self.ema50 = EMA(period=50)
        self.ema200 = EMA(period=200)
        self.adx_ind = ADX(period=14)
        self.supertrend_ind = Supertrend(atr_period=10, multiplier=3.0)
        self.ichimoku_ind = Ichimoku()
        self.obv = OBV()
        self.vwap = VWAP()
        self.cci_ind = CCI(period=20)
        self.williams_r = WilliamsR(period=14)
        self.ha = HeikinAshi()
        self.fib = FibonacciLevels(swing_lookback=50)
        self.pivot = PivotPoints()
        self.risk_manager = RiskManager(min_risk_reward=settings.MIN_RISK_REWARD_RATIO)
        self._latest_pattern = None

    def _calc_rsi_vote(self, closes: List[float]) -> Tuple[Optional[str], float]:
        self.rsi.calculate(closes)
        if not self.rsi.is_ready():
            return None, 0.0
        val = self.rsi.latest_value
        if val < 40:
            return "bull", max(0, (40 - val) / 40)
        elif val > 60:
            return "bear", max(0, (val - 60) / 40)
        return None, 0.0

    def _calc_macd_vote(self, closes: List[float]) -> Tuple[Optional[str], float]:
        self.macd_ind.calculate(closes)
        vals = self.macd_ind.get_macd_values()
        if not vals or not vals.get("histogram"):
            return None, 0.0
        hist = vals["histogram"]
        if len(hist) < 2:
            return None, 0.0
        if hist[-1] > 0 and hist[-1] > hist[-2]:
            return "bull", min(abs(hist[-1]) / (abs(hist[-1]) + 0.001), 0.9)
        elif hist[-1] < 0 and hist[-1] < hist[-2]:
            return "bear", min(abs(hist[-1]) / (abs(hist[-1]) + 0.001), 0.9)
        return None, 0.0

    def _calc_ema_vote(self, closes: List[float]) -> Tuple[Optional[str], float]:
        self.ema9.calculate(closes)
        self.ema21.calculate(closes)
        self.ema50.calculate(closes)
        self.ema200.calculate(closes)
        e9, e21, e50, e200 = (
            self.ema9.latest_value, self.ema21.latest_value,
            self.ema50.latest_value, self.ema200.latest_value
        )
        if any(v is None for v in [e9, e21, e50, e200]):
            return None, 0.0
        bull_score = sum([e9>e21, e21>e50, e50>e200]) / 3.0
        bear_score = sum([e9<e21, e21<e50, e50<e200]) / 3.0
        if bull_score >= 0.67:
            return "bull", bull_score
        elif bear_score >= 0.67:
            return "bear", bear_score
        return None, 0.0

    def _calc_supertrend_vote(self, highs, lows, closes) -> Tuple[Optional[str], float]:
        self.supertrend_ind.calculate_from_ohlc(highs, lows, closes)
        c = self.supertrend_ind.get_current()
        if c["trend"] == 1:
            return "bull", 0.80
        elif c["trend"] == -1:
            return "bear", 0.80
        return None, 0.0

    def _calc_ichimoku_vote(self, highs, lows, closes, price) -> Tuple[Optional[str], float]:
        self.ichimoku_ind.calculate_from_ohlc(highs, lows, closes)
        bull = self.ichimoku_ind.bullish_signal_strength(price)
        bear = self.ichimoku_ind.bearish_signal_strength(price)
        if bull > 0.50 and bull > bear:
            return "bull", bull
        elif bear > 0.50 and bear > bull:
            return "bear", bear
        return None, 0.0

    def _calc_volume_vote(self, closes, volumes) -> Tuple[Optional[str], float]:
        self.obv.calculate_from_cv(closes, volumes)
        if self.obv.is_rising(lookback=5):
            return "bull", 0.70
        elif self.obv.is_falling(lookback=5):
            return "bear", 0.70
        return None, 0.0

    def _calc_bollinger_vote(self, closes, price) -> Tuple[Optional[str], float]:
        self.bb.calculate(closes)
        bands = self.bb.get_bands()
        if not bands["upper"] or not bands["lower"]:
            return None, 0.0
        if self.bb.is_at_lower_band(price) and self.bb.is_expanding():
            return "bull", 0.65
        elif self.bb.is_at_upper_band(price) and self.bb.is_expanding():
            return "bear", 0.65
        return None, 0.0

    def _calc_cci_vote(self, highs, lows, closes) -> Tuple[Optional[str], float]:
        self.cci_ind.calculate_from_ohlc(highs, lows, closes)
        scores = self.cci_ind.get_signal_score()
        bs, brs = scores.get("bull_score", 0), scores.get("bear_score", 0)
        if bs > brs and bs > 0.3:
            return "bull", bs
        elif brs > bs and brs > 0.3:
            return "bear", brs
        return None, 0.0

    def _calc_williams_vote(self, highs, lows, closes) -> Tuple[Optional[str], float]:
        self.williams_r.calculate_from_ohlc(highs, lows, closes)
        scores = self.williams_r.get_signal_score()
        bs, brs = scores.get("bull_score", 0), scores.get("bear_score", 0)
        if bs > brs and bs > 0.3:
            return "bull", bs
        elif brs > bs and brs > 0.3:
            return "bear", brs
        return None, 0.0

    def _calc_candlestick_vote(self, opens, highs, lows, closes, volumes) -> Tuple[Optional[str], float]:
        if not settings.ENABLE_CANDLESTICK_PATTERNS:
            return None, 0.0
        pattern = detect_latest_candlestick_pattern(
            opens=opens,
            highs=highs,
            lows=lows,
            closes=closes,
            volumes=volumes,
        )
        if pattern is None:
            self._latest_pattern = None
            return None, 0.0
        if pattern["strength"] < settings.PATTERN_MIN_STRENGTH:
            self._latest_pattern = pattern
            return None, 0.0
        self._latest_pattern = pattern
        return ("bull", float(pattern["strength"])) if pattern["bias"] == "bull" else ("bear", float(pattern["strength"]))

    def analyze(self, candle_list: CandleList, regime: str = "trending") -> Optional[TradingSignal]:
        """Run all indicator votes and produce a confluence signal."""
        if not self._validate_candle_count(candle_list, 210):
            return None

        closes = candle_list.closes
        opens = candle_list.opens
        highs = candle_list.highs
        lows = candle_list.lows
        volumes = candle_list.volumes
        current_price = closes[-1]

        atr_values = self.atr.calculate_from_ohlc(highs, lows, closes)
        atr = atr_values[-1] if atr_values else current_price * 0.02

        votes: Dict[str, Tuple[Optional[str], float]] = {
            "rsi":        self._calc_rsi_vote(closes),
            "macd":       self._calc_macd_vote(closes),
            "ema_stack":  self._calc_ema_vote(closes),
            "supertrend": self._calc_supertrend_vote(highs, lows, closes),
            "ichimoku":   self._calc_ichimoku_vote(highs, lows, closes, current_price),
            "volume_obv": self._calc_volume_vote(closes, volumes),
            "bollinger":  self._calc_bollinger_vote(closes, current_price),
            "cci":        self._calc_cci_vote(highs, lows, closes),
            "williams_r": self._calc_williams_vote(highs, lows, closes),
            "candlestick": self._calc_candlestick_vote(opens, highs, lows, closes, volumes),
        }

        # Tally weighted scores
        bull_score = 0.0
        bear_score = 0.0
        bull_sources = 0
        bear_sources = 0
        high_prob_setup = False

        for name, (direction, score) in votes.items():
            weight = INDICATOR_WEIGHTS.get(name, 0.05)
            
            # Dynamic boost for high-confidence candlestick patterns
            if name == "candlestick" and score >= 0.70:
                weight = max(weight, 0.25)  # Boost weight significantly
                high_prob_setup = True
                
            if direction == "bull":
                bull_score += score * weight
                bull_sources += 1
            elif direction == "bear":
                bear_score += score * weight
                bear_sources += 1

        logger.debug(
            f"Confluence [{candle_list.symbol}]: "
            f"bull={bull_score:.3f}({bull_sources}src) bear={bear_score:.3f}({bear_sources}src)"
        )

        # Determine final direction
        signal_type = None
        confidence = 0.0

        if bull_sources >= self.min_sources and bull_score > bear_score:
            signal_type = SignalType.BUY
            # Normalize: max possible weighted score ≈ 1.0
            confidence = min(0.50 + bull_score * 0.45, 0.95)
            # Bonus for higher source count
            confidence += min((bull_sources - self.min_sources) * 0.02, 0.08)

        elif bear_sources >= self.min_sources and bear_score > bull_score:
            signal_type = SignalType.SELL
            confidence = min(0.50 + bear_score * 0.45, 0.95)
            confidence += min((bear_sources - self.min_sources) * 0.02, 0.08)

        if signal_type is None:
            return None

        direction = "long" if signal_type == SignalType.BUY else "short"

        # Use Fibonacci levels for TP targets
        fib_data = None
        try:
            fib_data = self.fib.calculate_from_ohlc(highs, lows, closes)
        except Exception:
            pass

        # Pivot points for SL snapping
        pivot_levels = None
        try:
            if len(closes) >= 2:
                pivot_levels = self.pivot.calculate_classic(
                    prev_high=max(highs[-2:]),
                    prev_low=min(lows[-2:]),
                    prev_close=closes[-2],
                )
        except Exception:
            pass

        tp, sl, meta = self.risk_manager.calculate_adaptive_tp_sl(
            entry_price=current_price,
            atr=atr,
            direction=direction,
            regime=regime,
            fib_levels=fib_data,
            pivot_levels=pivot_levels,
            high_probability=high_prob_setup,
        )

        if signal_type == SignalType.BUY and (tp <= current_price or sl >= current_price):
            return None
        if signal_type == SignalType.SELL and (tp >= current_price or sl <= current_price):
            return None

        active_indicators = [
            name for name, (dir, score) in votes.items()
            if dir == ("bull" if signal_type == SignalType.BUY else "bear")
        ]

        vote_summary = {
            name: {"direction": d, "score": round(s, 3)}
            for name, (d, s) in votes.items()
        }

        return self._create_signal(
            symbol=candle_list.symbol,
            signal_type=signal_type,
            entry_price=current_price,
            take_profit_price=tp,
            stop_loss_price=sl,
            confidence=min(confidence, 0.95),
            indicators_used=active_indicators,
            indicator_values={
                "bull_score": round(bull_score, 4),
                "bear_score": round(bear_score, 4),
                "bull_sources": bull_sources,
                "bear_sources": bear_sources,
                "total_sources_checked": len(votes),
                "votes": vote_summary,
                "ATR": round(atr, 6),
                "candlestick_pattern": self._latest_pattern,
                **meta,
            },
        )
