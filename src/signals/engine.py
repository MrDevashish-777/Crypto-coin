"""
Signal Generation Engine — Professional Grade v2.0

Orchestrates the full analysis pipeline:
1. Market Regime Detection (ADX + ATR + BB + EMAs)
2. Regime-aware strategy selection
3. All strategies run with ATR-adaptive TP/SL
4. Weighted multi-strategy consensus voting
5. Multi-timeframe confluence validation
6. LLM enhancement (optional)
7. Minimum R:R enforcement before signal emission
"""

from __future__ import annotations


import logging
import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

from src.data.data_fetcher import DataFetcher
from src.signals.signal import TradingSignal, SignalType
from src.signals.market_regime import MarketRegimeDetector, MarketRegime, RegimeResult
from config.constants import CRYPTO_PAIRS, TIMEFRAMES
from config.settings import settings
from src.llm.agent import LLMAgentFactory
from src.llm.context import ContextManager

# #region agent log
_debug_log_path = "/Users/parthshende/Downloads/Planitt-Inhouse-App/.cursor/debug-50440f.log"


def _debug_log(hypothesis_id: str, message: str, data: Dict[str, Any]) -> None:
    payload = {
        "sessionId": "50440f",
        "runId": "post-fix-3",
        "hypothesisId": hypothesis_id,
        "location": "Crypto Bot/src/signals/engine.py",
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(_debug_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception:
        pass


try:
    from src.database.db import SessionLocal
    from src.database.models import Signal as SignalModel, LLMTrainingSample
    DB_WRITE_AVAILABLE = True
    _debug_log("H12", "sqlalchemy_signal_import_ok", {"db_write_available": True})
except Exception as db_import_error:
    SessionLocal = None
    SignalModel = None
    LLMTrainingSample = None
    DB_WRITE_AVAILABLE = False
    _debug_log("H12", "sqlalchemy_signal_import_failed", {"error": str(db_import_error)})
# #endregion

# Import all strategies
from src.signals.strategies.rsi_strategy import RSIStrategy
from src.signals.strategies.macd_strategy import MACDStrategy
from src.signals.strategies.bollinger_squeeze_strategy import BollingerSqueezeStrategy
from src.signals.strategies.ema_trend_strategy import EMATrendStrategy
from src.signals.strategies.supertrend_strategy import SupertrendStrategy
from src.signals.strategies.ichimoku_strategy import IchimokuStrategy
from src.signals.strategies.volume_breakout_strategy import VolumeBreakoutStrategy
from src.signals.strategies.stochastic_rsi_strategy import StochasticRSIStrategy
from src.signals.strategies.confluence_strategy import ConfluenceStrategy
from src.signals.strategies.smart_money_strategy import SmartMoneyStrategy
from src.news.fetcher import NewsFetcher

import json

logger = logging.getLogger(__name__)


# Strategy weights for consensus voting (higher = more trusted)
STRATEGY_WEIGHTS = {
    "smart_money":      0.35,  # Highest weight for institutional setups
    "confluence":       0.20,
    "supertrend":       0.12,
    "ichimoku":         0.12,
    "ema_trend":        0.10,
    "volume_breakout":  0.10,
    "bollinger_squeeze":0.05,
    "stochastic_rsi":   0.05,
    "macd":             0.04,
    "rsi":              0.03,
}

# Which strategies work best in each regime
REGIME_STRATEGY_MAP = {
    MarketRegime.TRENDING_UP: [
        "smart_money", "supertrend", "ema_trend", "ichimoku", "macd", "volume_breakout", "confluence"
    ],
    MarketRegime.TRENDING_DOWN: [
        "smart_money", "supertrend", "ema_trend", "ichimoku", "macd", "volume_breakout", "confluence"
    ],
    MarketRegime.RANGING: [
        "smart_money", "rsi", "bollinger_squeeze", "stochastic_rsi", "confluence"
    ],
    MarketRegime.VOLATILE: [
        "smart_money", "bollinger_squeeze", "rsi", "confluence"
    ],
    MarketRegime.UNKNOWN: ["smart_money", "rsi", "macd", "confluence"],
}


class SignalEngine:
    """
    Professional-grade signal generation engine.

    Pipeline for each symbol:
    1. Fetch OHLCV candle data
    2. Detect market regime
    3. Select strategies appropriate for regime
    4. Run strategies → collect signals
    5. Weight and aggregate via consensus voting
    6. Optional: LLM enhancement
    7. Validate R:R >= minimum before emitting
    """

    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.context_manager = ContextManager()
        self.regime_detector = MarketRegimeDetector()
        self.news_fetcher = NewsFetcher()
        self._news_cache = []
        self._news_cache_time = 0

        # LLM Agent
        self.llm_agent = LLMAgentFactory.create_agent(
            provider=settings.LLM_PROVIDER,
            api_key=getattr(settings, f"{settings.LLM_PROVIDER.upper()}_API_KEY", None),
            model=getattr(settings, f"{settings.LLM_PROVIDER.upper()}_MODEL", None),
            base_url=settings.OLLAMA_BASE_URL if settings.LLM_PROVIDER == "ollama" else None
        )

        # All strategies — instantiated once and reused
        self.strategies = {
            "rsi":              RSIStrategy(),
            "macd":             MACDStrategy(),
            "bollinger_squeeze": BollingerSqueezeStrategy(),
            "ema_trend":        EMATrendStrategy(),
            "supertrend":       SupertrendStrategy(),
            "ichimoku":         IchimokuStrategy(),
            "volume_breakout":  VolumeBreakoutStrategy(),
            "stochastic_rsi":   StochasticRSIStrategy(),
            "confluence":       ConfluenceStrategy(),
            "smart_money":      SmartMoneyStrategy(),
        }

        self.generated_signals: Dict[str, List[TradingSignal]] = {}
        logger.info(f"SignalEngine v2.0 initialized | {len(self.strategies)} strategies | LLM: {settings.LLM_PROVIDER}")

    # ==============================================================
    # MAIN ENTRY: Generate signal for a symbol
    # ==============================================================

    async def generate_signal(
        self,
        symbol: str,
        timeframe: str = "1h",
        strategy: str = "confluence",
    ) -> Optional[TradingSignal]:
        """
        Generate a single strategy signal for a symbol.

        Args:
            symbol: Crypto pair (e.g. 'BTC')
            timeframe: Candle timeframe
            strategy: Strategy name to use

        Returns:
            TradingSignal or None
        """
        try:
            if symbol not in CRYPTO_PAIRS:
                raise ValueError(f"Unsupported symbol: {symbol}")
            if timeframe not in TIMEFRAMES:
                raise ValueError(f"Unsupported timeframe: {timeframe}")
            if strategy not in self.strategies:
                raise ValueError(f"Unknown strategy: {strategy}")

            # Fetch candles
            candle_list = await self.data_fetcher.fetch_candles(symbol=symbol, timeframe=timeframe, limit=500)

            # Detect market regime
            regime_result = self.regime_detector.detect(candle_list)
            regime_str = regime_result.regime.value

            # Run strategy
            strategy_obj = self.strategies[strategy]
            # Pass regime to analysis where supported
            try:
                signal = strategy_obj.analyze(candle_list, regime=regime_str)
            except TypeError:
                signal = strategy_obj.analyze(candle_list)

            if signal and signal.confidence >= settings.MIN_SIGNAL_CONFIDENCE:
                # Validate R:R
                if signal.risk_reward_ratio < settings.MIN_RISK_REWARD_RATIO:
                    logger.warning(
                        f"Signal for {symbol} rejected: R:R={signal.risk_reward_ratio:.2f} "
                        f"< minimum {settings.MIN_RISK_REWARD_RATIO}"
                    )
                    return None

                # Optional LLM enhancement
                if settings.ENABLE_LLM_ANALYSIS:
                    signal = await self._enhance_with_llm(signal, candle_list, regime_result)
                    if signal is None:
                        return None

                # Store and persist
                key = f"{symbol}_{timeframe}_{strategy}"
                self.generated_signals.setdefault(key, []).append(signal)
                self._save_signal_to_db(signal)

                logger.info(
                    f"[{strategy.upper()}] {signal.signal_type.value.upper()} {symbol} "
                    f"| Conf: {signal.confidence:.2%} | R:R: {signal.risk_reward_ratio:.2f} "
                    f"| Regime: {regime_str}"
                )
                return signal

            return None

        except Exception as e:
            logger.error(f"Error generating signal for {symbol}: {str(e)}")
            raise

    # ==============================================================
    # SMART SIGNAL: Regime-aware multi-strategy consensus
    # ==============================================================

    async def smart_signal(
        self,
        symbol: str,
        timeframe: str = "1h",
    ) -> Optional[TradingSignal]:
        """
        Generate a consensus signal using all strategies appropriate for the detected regime.

        Steps:
        1. Detect market regime
        2. Select regime-appropriate strategies
        3. Run all selected strategies
        4. Weighted voting to produce final signal
        5. Enforce minimum R:R

        Returns:
            Best consensus signal, or None if no agreement
        """
        logger.info(f"Running smart_signal for {symbol} [{timeframe}]")

        candle_list = await self.data_fetcher.fetch_candles(symbol=symbol, timeframe=timeframe, limit=500)

        # Detect regime
        regime_result = self.regime_detector.detect(candle_list)
        regime_str = regime_result.regime.value
        logger.info(f"[{symbol}] Regime: {regime_str} (confidence: {regime_result.confidence:.2%})")

        # Get preferred strategies for regime
        preferred = REGIME_STRATEGY_MAP.get(regime_result.regime, list(self.strategies.keys()))

        # Run all preferred strategies
        signals: Dict[str, TradingSignal] = {}
        for strat_name in preferred:
            strat = self.strategies.get(strat_name)
            if strat is None:
                continue
            try:
                try:
                    sig = strat.analyze(candle_list, regime=regime_str)
                except TypeError:
                    sig = strat.analyze(candle_list)

                if sig and sig.confidence >= settings.MIN_SIGNAL_CONFIDENCE:
                    signals[strat_name] = sig
            except Exception as e:
                logger.error(f"Strategy {strat_name} failed for {symbol}: {str(e)}")

        if not signals:
            return None

        # Weighted consensus voting
        return self._weighted_consensus(symbol, timeframe, signals, regime_result)

    def _weighted_consensus(
        self,
        symbol: str,
        timeframe: str,
        signals: Dict[str, TradingSignal],
        regime_result: RegimeResult,
    ) -> Optional[TradingSignal]:
        """Produce a consensus signal from multiple strategy signals using weighted voting."""
        buy_weight = 0.0
        sell_weight = 0.0
        buy_signals = []
        sell_signals = []

        for strat_name, sig in signals.items():
            weight = STRATEGY_WEIGHTS.get(strat_name, 0.05)
            weighted_conf = sig.confidence * weight
            if sig.signal_type == SignalType.BUY:
                buy_weight += weighted_conf
                buy_signals.append((strat_name, sig, weight))
            elif sig.signal_type == SignalType.SELL:
                sell_weight += weighted_conf
                sell_signals.append((strat_name, sig, weight))

        # No clear consensus
        if buy_weight == 0 and sell_weight == 0:
            return None

        if buy_weight > sell_weight:
            winning_signals = buy_signals
            direction = SignalType.BUY
            total_weight = buy_weight
        else:
            winning_signals = sell_signals
            direction = SignalType.SELL
            total_weight = sell_weight

        if not winning_signals:
            return None

        # Select the highest-confidence signal as representative
        best_sig = max(winning_signals, key=lambda x: x[1].confidence * x[2])
        best_signal = best_sig[1]

        # Enforce minimum R:R
        if best_signal.risk_reward_ratio < settings.MIN_RISK_REWARD_RATIO:
            logger.warning(
                f"Consensus signal for {symbol} rejected due to low R:R: {best_signal.risk_reward_ratio:.2f}"
            )
            return None

        # Boost confidence if multiple strategies agree
        num_agreeing = len(winning_signals)
        confidence_boost = min(num_agreeing * 0.03, 0.15)
        best_signal.confidence = min(best_signal.confidence + confidence_boost, 0.97)
        best_signal.strategy_name = (
            f"Smart Consensus ({num_agreeing} strategies agree | Regime: {regime_result.regime.value})"
        )

        # Enrich with regime info
        if best_signal.indicator_values is None:
            best_signal.indicator_values = {}
        best_signal.indicator_values.update({
            "regime": regime_result.regime.value,
            "adx": regime_result.adx,
            "buy_weight": round(buy_weight, 4),
            "sell_weight": round(sell_weight, 4),
            "strategies_agreeing": [s[0] for s in winning_signals],
            "regime_confidence": regime_result.confidence,
        })

        logger.info(
            f"[CONSENSUS] {direction.value.upper()} {symbol} "
            f"| {num_agreeing} strategies | Conf: {best_signal.confidence:.2%} "
            f"| Regime: {regime_result.regime.value}"
        )

        key = f"{symbol}_{timeframe}_smart"
        self.generated_signals.setdefault(key, []).append(best_signal)
        self._save_signal_to_db(best_signal)
        return best_signal

    # ==============================================================
    # MULTI-TIMEFRAME ANALYSIS
    # ==============================================================

    async def multi_timeframe_signal(self, symbol: str) -> Optional[TradingSignal]:
        """
        Generate a signal that requires alignment across 3 timeframes.

        4h = Trend direction (must match)
        1h = Trend confirmation (must match)
        15m = Entry timing (actual signal)

        Only emits a signal if all 3 timeframes agree on direction.
        TP/SL sized from the 4h ATR (larger levels = more room).
        """
        logger.info(f"Running multi-timeframe analysis for {symbol}")

        primary_tf = settings.MTF_PRIMARY_TIMEFRAME
        secondary_tf = settings.MTF_SECONDARY_TIMEFRAME
        entry_tf = settings.MTF_ENTRY_TIMEFRAME

        try:
            primary_candles, secondary_candles, entry_candles = await asyncio.gather(
                self.data_fetcher.fetch_candles(symbol, primary_tf, limit=300),
                self.data_fetcher.fetch_candles(symbol, secondary_tf, limit=300),
                self.data_fetcher.fetch_candles(symbol, entry_tf, limit=300),
            )
        except Exception as e:
            logger.error(f"MTF fetch failed for {symbol}: {str(e)}")
            return None

        # Detect regime on each timeframe
        primary_regime = self.regime_detector.detect(primary_candles)
        secondary_regime = self.regime_detector.detect(secondary_candles)

        # Get directional bias per timeframe
        def get_bias(regime: RegimeResult) -> Optional[str]:
            if regime.regime == MarketRegime.TRENDING_UP:
                return "bull"
            elif regime.regime == MarketRegime.TRENDING_DOWN:
                return "bear"
            return None

        primary_bias = get_bias(primary_regime)
        secondary_bias = get_bias(secondary_regime)

        if not primary_bias or not secondary_bias or primary_bias != secondary_bias:
            logger.debug(f"MTF: No alignment for {symbol} ({primary_bias} / {secondary_bias})")
            return None

        # Both higher timeframes agree — now get entry signal on 15m
        entry_regime = self.regime_detector.detect(entry_candles)
        entry_regime_str = entry_regime.regime.value

        # Run preferred strategies on entry timeframe
        preferred = REGIME_STRATEGY_MAP.get(entry_regime.regime, ["rsi", "macd", "confluence"])
        signals = {}
        for strat_name in preferred:
            strat = self.strategies.get(strat_name)
            if strat is None:
                continue
            try:
                try:
                    sig = strat.analyze(entry_candles, regime=entry_regime_str)
                except TypeError:
                    sig = strat.analyze(entry_candles)

                if sig and sig.signal_type.value == ("buy" if primary_bias == "bull" else "sell"):
                    if sig.confidence >= settings.MIN_SIGNAL_CONFIDENCE:
                        signals[strat_name] = sig
            except Exception as e:
                logger.error(f"MTF strategy error {strat_name}: {str(e)}")

        if not signals:
            return None

        mtf_signal = self._weighted_consensus(symbol, entry_tf, signals, entry_regime)
        if mtf_signal:
            mtf_signal.strategy_name = (
                f"MTF Confluence ({primary_tf}↑{secondary_tf}↑{entry_tf} | {primary_bias.upper()})"
            )
            if mtf_signal.indicator_values is None:
                mtf_signal.indicator_values = {}
            mtf_signal.indicator_values["mtf_primary_regime"] = primary_regime.regime.value
            mtf_signal.indicator_values["mtf_secondary_regime"] = secondary_regime.regime.value
            mtf_signal.confidence = min(mtf_signal.confidence + 0.08, 0.97)

        return mtf_signal

    # ==============================================================
    # GENERATE ALL SYMBOLS
    # ==============================================================

    async def generate_all_signals(
        self,
        timeframe: str = "1h",
        strategy: str = "smart",
    ) -> Dict[str, Optional[TradingSignal]]:
        """Generate signals for all supported symbols."""
        logger.info(f"Scanning all symbols [{timeframe}] with strategy: {strategy}")
        symbols = list(CRYPTO_PAIRS.keys())

        if strategy == "smart":
            tasks = [self.smart_signal(symbol, timeframe) for symbol in symbols]
        elif strategy == "mtf":
            tasks = [self.multi_timeframe_signal(symbol) for symbol in symbols]
        else:
            tasks = [self.generate_signal(symbol, timeframe, strategy) for symbol in symbols]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        signals = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"Failed for {symbol}: {str(result)}")
            else:
                signals[symbol] = result

        n_signals = sum(1 for s in signals.values() if s is not None)
        logger.info(f"Generated {n_signals} signals from {len(symbols)} symbols")
        return signals

    # ==============================================================
    # LEGACY: Kept for backward compatibility with existing API routes
    # ==============================================================

    async def multi_strategy_signal(self, symbol: str, timeframe: str = "15m") -> Optional[TradingSignal]:
        """Backward-compatible alias for smart_signal()."""
        return await self.smart_signal(symbol, timeframe)

    async def get_llm_analysis(self, symbol: str, timeframe: str = "1h") -> Dict:
        """Get LLM analysis for a symbol (original method, kept for API compatibility)."""
        try:
            candles = await self.data_fetcher.fetch_candles(symbol, timeframe, limit=100)
            if not candles:
                return {"error": "No data available"}

            from src.indicators.rsi import RSI
            from src.indicators.macd import MACD
            from src.indicators.atr import ATR

            closes = candles.closes
            highs = candles.highs
            lows = candles.lows

            rsi_ind = RSI()
            rsi_ind.calculate(closes)
            rsi_val = rsi_ind.latest_value or 50

            macd_ind = MACD()
            histogram = macd_ind.calculate(closes)
            macd_vals = macd_ind.get_macd_values()
            macd_val = macd_vals["macd_line"][-1] if macd_vals and macd_vals.get("macd_line") else 0

            atr_ind = ATR()
            atr_vals = atr_ind.calculate_from_ohlc(highs, lows, closes)
            atr_val = atr_vals[-1] if atr_vals else 0

            # Detect regime for context
            regime = self.regime_detector.detect(candles)

            last_price = closes[-1]
            change_24h = ((last_price - closes[0]) / closes[0]) * 100 if closes else 0

            market_data = {
                "symbol": symbol,
                "price": last_price,
                "change_24h": round(change_24h, 2),
                "volume": candles.candles[-1].volume if candles.candles else 0,
                "rsi": round(rsi_val, 2),
                "macd": round(macd_val, 6),
                "atr": round(atr_val, 6),
                "atr_pct": round(atr_val / last_price * 100, 3) if last_price else 0,
                "regime": regime.regime.value,
                "adx": regime.adx,
                "timeframe": timeframe,
            }

            context = self.context_manager.get_historical_context(symbol)
            analysis = await self.llm_agent.analyze_market(market_data, context=context)

            if not isinstance(analysis, dict):
                return {"error": "Invalid LLM response format"}

            self._save_training_sample(market_data, analysis, context)
            analysis["price"] = last_price
            return analysis

        except Exception as e:
            logger.error(f"LLM analysis failed for {symbol}: {str(e)}")
            return {"error": str(e)}

    async def generate_ai_signal(self, symbol: str, timeframe: str = "1h") -> Optional[TradingSignal]:
        """LLM-driven signal generation (kept for API compatibility)."""
        try:
            analysis = await self.get_llm_analysis(symbol, timeframe)
            confidence = float(analysis.get("confidence", 0.0))

            if confidence >= settings.MIN_SIGNAL_CONFIDENCE:
                sentiment = analysis.get("sentiment", "neutral").lower()
                if sentiment not in ["bullish", "bearish"]:
                    return None

                price = analysis.get("price")
                if not price:
                    candles = await self.data_fetcher.fetch_candles(symbol, timeframe, limit=2, min_candles=1)
                    price = candles.candles[-1].close if candles.candles else None
                if not price:
                    return None

                from src.indicators.atr import ATR
                candles = await self.data_fetcher.fetch_candles(symbol, timeframe, limit=100)
                atr_ind = ATR()
                atr_vals = atr_ind.calculate_from_ohlc(candles.highs, candles.lows, candles.closes)
                atr = atr_vals[-1] if atr_vals else price * 0.02

                regime_result = self.regime_detector.detect(candles)

                from src.risk.risk_manager import RiskManager
                from src.signals.signal import TargetLevel, SignalStrength

                rm = RiskManager(min_risk_reward=settings.MIN_RISK_REWARD_RATIO)
                direction = "long" if sentiment == "bullish" else "short"
                tp, sl, meta = rm.calculate_adaptive_tp_sl(
                    entry_price=price,
                    atr=atr,
                    direction=direction,
                    regime=regime_result.regime.value,
                )

                signal_type = SignalType.BUY if sentiment == "bullish" else SignalType.SELL

                # Validate
                if signal_type == SignalType.BUY and (tp <= price or sl >= price):
                    return None
                if signal_type == SignalType.SELL and (tp >= price or sl <= price):
                    return None

                signal = TradingSignal(
                    symbol=symbol,
                    timeframe=timeframe,
                    signal_type=signal_type,
                    entry_price=price,
                    take_profit=TargetLevel(
                        price=tp,
                        percent_from_entry=abs(tp - price) / price * 100,
                        label="Take Profit"
                    ),
                    stop_loss=TargetLevel(
                        price=sl,
                        percent_from_entry=abs(sl - price) / price * 100,
                        label="Stop Loss"
                    ),
                    position_size=rm.calculate_position_size_percent(price, sl),
                    confidence=confidence,
                    strength=SignalStrength.STRONG if confidence > 0.8 else SignalStrength.NEUTRAL,
                    timestamp=int(datetime.utcnow().timestamp() * 1000),
                    generated_at=datetime.utcnow().isoformat(),
                    indicators_used=["LLM", "ATR"],
                    llm_confidence=confidence,
                    llm_sentiment=sentiment,
                    llm_analysis=analysis.get("reasoning", ""),
                    strategy_name="AI Research Analyst",
                    indicator_values={**meta, "regime": regime_result.regime.value},
                )

                key = f"{symbol}_{timeframe}_ai"
                self.generated_signals.setdefault(key, []).append(signal)
                self._save_signal_to_db(signal)
                return signal

            return None
        except Exception as e:
            logger.error(f"AI signal failed for {symbol}: {str(e)}")
            return None

    async def get_market_status(self) -> List[Dict]:
        """Get current market status for all supported cryptos."""
        symbols = settings.SUPPORTED_CRYPTOS
        tasks = [self.data_fetcher.fetch_candles(symbol, "1d", limit=2, min_candles=2) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        status = []
        for symbol, candles in zip(symbols, results):
            if isinstance(candles, Exception) or not candles:
                continue
            last = candles.candles[-1]
            first = candles.candles[0]
            price = last.close
            change = ((price - first.close) / first.close) * 100
            status.append({
                "symbol": symbol,
                "price": round(price, 4),
                "change": round(change, 2),
                "volume": round(last.volume, 2),
            })
        return status

    def get_signal_history(
        self, symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> List[TradingSignal]:
        """Get historical generated signals."""
        signals = []
        for key, signal_list in self.generated_signals.items():
            parts = key.split("_")
            sig_symbol, sig_timeframe = parts[0], parts[1] if len(parts) > 1 else ""
            if symbol and sig_symbol != symbol:
                continue
            if timeframe and sig_timeframe != timeframe:
                continue
            signals.extend(signal_list)
        signals.sort(key=lambda s: s.timestamp, reverse=True)
        return signals

    async def close(self):
        await self.data_fetcher.close()
        logger.info("SignalEngine closed")

    # ==============================================================
    # PRIVATE HELPERS
    # ==============================================================

    async def _enhance_with_llm(
        self, signal: TradingSignal, candle_list, regime_result: RegimeResult
    ) -> Optional[TradingSignal]:
        """Optionally enhance signal with LLM analysis."""
        try:
            closes = candle_list.closes
            highs = candle_list.highs
            lows = candle_list.lows

            from src.indicators.rsi import RSI
            from src.indicators.macd import MACD
            from src.indicators.atr import ATR

            rsi_ind = RSI()
            rsi_ind.calculate(closes)

            atr_ind = ATR()
            atr_vals = atr_ind.calculate_from_ohlc(highs, lows, closes)

            market_data = {
                "symbol": signal.symbol,
                "price": signal.entry_price,
                "change_24h": round(((closes[-1] - closes[0]) / closes[0]) * 100, 2),
                "volume": candle_list.candles[-1].volume if candle_list.candles else 0,
                "rsi": round(rsi_ind.latest_value or 50, 2),
                "atr": round(atr_vals[-1] if atr_vals else 0, 6),
                "regime": regime_result.regime.value,
                "strategy": signal.strategy_name,
                "confidence": signal.confidence,
                "timeframe": signal.timeframe,
            }

            context = self.context_manager.get_historical_context(signal.symbol)
            
            # Fetch recent news related to this symbol
            all_news = await self._get_cached_news()
            token = signal.symbol.replace("USDT", "")
            symbol_news = [
                n for n in all_news
                if signal.symbol in n.get("symbols", []) or token in n.get("symbols", [])
            ]
            if symbol_news:
                news_context = "\nRecent News for this symbol:\n"
                for n in symbol_news[:3]:
                    news_context += f"- {n.get('headline')} ({n.get('sentiment')})\n"
                context += "\n" + news_context

            llm_analysis = await self.llm_agent.analyze_market(market_data, context=context)

            if not isinstance(llm_analysis, dict):
                return signal  # Keep original signal

            llm_confidence = float(llm_analysis.get("confidence", 0.0))
            signal.llm_analysis = llm_analysis.get("reasoning", "")
            signal.llm_sentiment = llm_analysis.get("sentiment", "neutral")
            signal.llm_confidence = llm_confidence

            # Weighted blend: 60% technical, 40% LLM
            signal.confidence = min((signal.confidence * 0.6) + (llm_confidence * 0.4), 0.97)

            if signal.confidence < settings.LLM_ANALYSIS_THRESHOLD:
                logger.warning(f"Signal rejected after LLM review: confidence={signal.confidence:.2%}")
                return None

            return signal
        except Exception as e:
            logger.error(f"LLM enhancement failed: {str(e)}")
            return signal  # Return original signal if LLM fails

    def _save_training_sample(self, market_data: Dict, analysis: Dict, context: str):
        """Save market data + LLM analysis pair for training."""
        if not DB_WRITE_AVAILABLE or SessionLocal is None or LLMTrainingSample is None:
            # #region agent log
            _debug_log("H12", "skip_save_training_sample", {"reason": "db_write_unavailable"})
            # #endregion
            return
        try:
            sentiment = analysis.get("sentiment", "neutral").lower()
            label_map = {"bearish": 0, "neutral": 1, "bullish": 2}
            label = label_map.get(sentiment, 1)
            input_text = (
                f"Symbol: {market_data.get('symbol')} | Price: {market_data.get('price')} "
                f"| RSI: {market_data.get('rsi')} | MACD: {market_data.get('macd', 0)} "
                f"| ATR: {market_data.get('atr', 0)} | Regime: {market_data.get('regime', 'unknown')} "
                f"| Change: {market_data.get('change_24h')}% | Context: {context[:500]}"
            )
            db = SessionLocal()
            sample = LLMTrainingSample(
                symbol=market_data.get("symbol"),
                input_text=input_text,
                label=label,
                llm_provider=settings.LLM_PROVIDER,
                confidence=float(analysis.get("confidence", 0.0)),
            )
            db.add(sample)
            db.commit()
            db.close()
        except Exception as e:
            logger.error(f"Failed to save training sample: {str(e)}")

    def _save_signal_to_db(self, signal: TradingSignal):
        """Save signal to database."""
        if not DB_WRITE_AVAILABLE or SessionLocal is None or SignalModel is None:
            # #region agent log
            _debug_log("H12", "skip_save_signal", {"symbol": signal.symbol, "reason": "db_write_unavailable"})
            # #endregion
            return
        db = SessionLocal()
        try:
            db_signal = SignalModel(
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                signal_type=signal.signal_type.value,
                entry_price=signal.entry_price,
                take_profit=signal.take_profit.price if signal.take_profit else None,
                stop_loss=signal.stop_loss.price if signal.stop_loss else None,
                confidence=signal.confidence,
                strategy_name=signal.strategy_name,
                indicators_used=signal.indicators_used,
                indicator_values=signal.indicator_values,
                generated_at=datetime.fromisoformat(signal.generated_at)
                if isinstance(signal.generated_at, str)
                else datetime.utcnow(),
            )
            db.add(db_signal)
            db.commit()
            logger.debug(f"Signal for {signal.symbol} saved to database")
        except Exception as e:
            logger.error(f"Failed to save signal to database: {str(e)}")
            db.rollback()
        finally:
            db.close()

    async def _get_cached_news(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Fetch news and cache for 15 minutes to avoid excessive API calls."""
        now = time.time()
        if force_refresh or not self._news_cache or now - self._news_cache_time > 900:  # 15 minutes
            try:
                self._news_cache = await self.news_fetcher.fetch_all_news(limit_per_feed=20)
                self._news_cache_time = now
            except Exception as e:
                logger.error(f"Failed to fetch cached news: {str(e)}")
        return self._news_cache

    async def get_market_news(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Fetch latest crypto news and analyze sentiment."""
        logger.info(f"Fetching latest market news (limit: {limit})...")
        try:
            news_items = await self._get_cached_news()
            # Limit total items to analyze to avoid excessive API calls
            news_items = news_items[:limit]

            if not news_items:
                return []

            # Analyze sentiment for each news item
            tasks = [self._analyze_news_sentiment(item) for item in news_items]
            analyzed_news = await asyncio.gather(*tasks)
            
            return analyzed_news
        except Exception as e:
            logger.error(f"Error in get_market_news: {str(e)}")
            return []

    async def _analyze_news_sentiment(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze sentiment of a single news item using the dedicated LLM agent method."""
        try:
            headline = item.get("headline", "")
            summary = item.get("summary", "")
            text_to_analyze = f"Headline: {headline}\nSummary: {summary}"
            
            analysis = await self.llm_agent.analyze_news_sentiment(text_to_analyze)
            
            item["sentiment"] = analysis.get("sentiment", "neutral").upper()
            item["confidence"] = analysis.get("confidence", 0.0)
            return item
        except Exception as e:
            logger.error(f"Sentiment analysis failed for news: {str(e)}")
            item["sentiment"] = "NEUTRAL"
            item["confidence"] = 0.0
            return item
