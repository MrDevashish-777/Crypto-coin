import logging
from typing import List

from config.settings import settings
from src.planitt.rules.base import ConfluenceRule, RuleContext
from src.planitt.confluence import ConfluenceFeatures, ConfluenceEvaluation

logger = logging.getLogger(__name__)

class ConfluencePipeline:
    def __init__(self, rules: List[ConfluenceRule]):
        self.rules = rules

    def evaluate(self, context: RuleContext) -> ConfluenceEvaluation:
        # Run rules sequentially
        for rule in self.rules:
            result = rule.evaluate(context)
            if not result.passed:
                return ConfluenceEvaluation(
                    features=None, 
                    reject_reason=result.reason
                )
        
        # All rules passed, build ConfluenceFeatures from context
        merged_hits = list(dict.fromkeys(context.confluence_hits + list(context.vote_hits)))
        
        from src.advisor.segment_gates import get_publish_thresholds
        segment_min_hits = get_publish_thresholds(context.side, context.candle_list.timeframe).min_confluence_hits
        
        effective_min_hits = context.min_confluence_hits
        adx_val = context.regime_result.adx or 0.0
        if adx_val >= context.adx_trend_threshold + 2:
            effective_min_hits = min(settings.PLANITT_MIN_HITS_STRONG_ADX, context.min_confluence_hits)
        effective_min_hits = min(effective_min_hits, segment_min_hits)

        if len(merged_hits) < effective_min_hits:
            return ConfluenceEvaluation(
                features=None,
                reject_reason=f"confluence_hits_too_low:{len(merged_hits)}",
            )
            
        base_conf = min(0.95, 0.40 + (len(context.confluence_hits) * 0.08) + (max(0.0, context.volume_ratio - 1.0) * 0.06))
        if context.pattern_strength > 0 and context.pattern_confirmed:
            base_conf = min(0.97, base_conf + min(context.pattern_strength * 0.06, 0.05))
        pre_conf = min(0.97, 0.35 * base_conf + 0.65 * context.pre_confidence)

        features = ConfluenceFeatures(
            asset=context.candle_list.symbol,
            timeframe=context.candle_list.timeframe,
            side=context.side,
            setup_type=context.setup_type,
            price=context.price,
            atr=context.atr,
            ema20=float(context.ema20),
            ema50=float(context.ema50),
            ema200=float(context.ema200),
            rsi=float(context.rsi),
            macd_hist=float(context.macd_hist),
            macd_hist_prev=float(context.macd_hist_prev),
            volume=context.current_volume,
            volume_ratio=float(context.volume_ratio),
            key_level=float(context.key_level),
            breakout_level=float(context.breakout_level) if context.breakout_level is not None else None,
            confluence_hits=tuple(merged_hits),
            pre_confidence=float(pre_conf),
            adx=context.regime_result.adx,
            candlestick_pattern=context.pattern_name,
            candlestick_bias=context.pattern_bias,
            candlestick_strength=context.pattern_strength,
            candlestick_confirmed=context.pattern_confirmed,
            agreeing_sources=context.agreeing_sources,
            mtf_score=0.0,
        )
        return ConfluenceEvaluation(features=features, reject_reason=None)
