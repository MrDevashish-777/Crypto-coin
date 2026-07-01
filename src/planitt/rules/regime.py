from typing import Optional, Tuple
from config.settings import settings
from src.signals.market_regime import MarketRegimeDetector, MarketRegime
from src.planitt.rules.base import ConfluenceRule, RuleContext, RuleResult

def _regime_allows_entry(regime_result, *, adx_trend_threshold: float) -> Tuple[bool, Optional[str]]:
    """Allow trending or directional ranging (ADX + DI) instead of blocking all chop."""
    adx = regime_result.adx
    if adx is None or adx < adx_trend_threshold:
        return False, None

    if regime_result.regime != MarketRegime.RANGING:
        return True, None

    if not settings.PLANITT_ALLOW_RANGING_WITH_DIRECTION:
        return False, None

    pd = regime_result.plus_di
    md = regime_result.minus_di
    if pd is None or md is None:
        return False, None
    if abs(pd - md) >= settings.PLANITT_RANGING_MIN_DI_SPREAD:
        return True, "directional_ranging"
    # ADX above threshold but classified ranging (common on alts in chop)
    if adx >= adx_trend_threshold + 2:
        return True, "adx_ranging"
    return False, None


class MarketRegimeRule(ConfluenceRule):
    """
    Evaluates market regime and ADX threshold. 
    Updates context with regime_result and regime_tag.
    """
    def evaluate(self, context: RuleContext) -> RuleResult:
        regime_detector = MarketRegimeDetector()
        regime_result = regime_detector.detect(context.candle_list)
        context.regime_result = regime_result
        
        regime_ok, regime_tag = _regime_allows_entry(
            regime_result, 
            adx_trend_threshold=context.adx_trend_threshold
        )
        context.regime_tag = regime_tag
        
        if not regime_ok:
            if regime_result.regime == MarketRegime.VOLATILE and not settings.PLANITT_ALLOW_VOLATILE_THROUGH_GATES:
                return RuleResult.reject(f"regime_filtered:{regime_result.regime.value}")
                
            if (
                regime_result.regime == MarketRegime.RANGING
                and settings.PLANITT_ALLOW_RANGING_WITH_DIRECTION
            ):
                adx = regime_result.adx
                pd = regime_result.plus_di
                md = regime_result.minus_di
                di_spread = abs(pd - md) if pd is not None and md is not None else 0.0
                directional = di_spread >= settings.PLANITT_RANGING_MIN_DI_SPREAD
                adx_ranging = adx is not None and adx >= context.adx_trend_threshold + 2
                
                if adx is None or adx < context.adx_trend_threshold:
                    return RuleResult.reject(f"adx_below_threshold:{adx}")
                if not directional and not adx_ranging:
                    return RuleResult.reject("ranging_no_direction")
            else:
                return RuleResult.reject(f"adx_below_threshold:{regime_result.adx}")
                
        if regime_tag:
            context.confluence_hits.append(regime_tag)
            
        return RuleResult.ok()
