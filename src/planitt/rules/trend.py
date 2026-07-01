from config.settings import settings
from src.planitt.rules.base import ConfluenceRule, RuleContext, RuleResult
from src.indicators.ema import EMA
from src.planitt.crypto_futures_analysis import infer_trade_side
from src.advisor.segment_gates import validate_sell_regime

def _find_pivots(values: list[float], *, is_high: bool) -> list[tuple[int, float]]:
    if len(values) < 3:
        return []
    pivots: list[tuple[int, float]] = []
    for i in range(1, len(values) - 1):
        prev_v = values[i - 1]
        curr_v = values[i]
        next_v = values[i + 1]
        if is_high and curr_v > prev_v and curr_v > next_v:
            pivots.append((i, curr_v))
        if not is_high and curr_v < prev_v and curr_v < next_v:
            pivots.append((i, curr_v))
    return pivots

def _swing_structure_ok(highs: list[float], lows: list[float], *, side: str) -> bool:
    window = min(settings.PLANITT_SWING_PIVOT_LOOKBACK, len(highs))
    highs_w = highs[-window:]
    lows_w = lows[-window:]

    piv_highs = _find_pivots(highs_w, is_high=True)
    piv_lows = _find_pivots(lows_w, is_high=False)

    if len(piv_highs) < 2 or len(piv_lows) < 2:
        return False

    last2_highs = piv_highs[-2:]
    last2_lows = piv_lows[-2:]

    h1, h2 = last2_highs[0][1], last2_highs[1][1]
    l1, l2 = last2_lows[0][1], last2_lows[1][1]

    if side == "BUY":
        return h2 > h1 and l2 > l1
    return h2 < h1 and l2 < l1

def _swing_structure_required(adx: float | None, timeframe: str = "1h") -> bool:
    if timeframe in ("4h", "1d") and settings.ADVISOR_SWING_REQUIRE_STRUCTURE:
        return True
    if not settings.PLANITT_REQUIRE_SWING_STRUCTURE:
        return False
    if adx is None:
        return True
    return adx < settings.PLANITT_SWING_STRICT_ADX_MAX

class TrendAlignmentRule(ConfluenceRule):
    """
    Evaluates EMA alignment and swing structure.
    Updates context with side, EMA values, and structure info.
    """
    def evaluate(self, context: RuleContext) -> RuleResult:
        closes = context.candle_list.closes
        highs = context.candle_list.highs
        lows = context.candle_list.lows
        
        ema20_ind = EMA(period=20)
        ema50_ind = EMA(period=50)
        ema200_ind = EMA(period=200)
        ema20_ind.calculate(closes)
        ema50_ind.calculate(closes)
        ema200_ind.calculate(closes)

        context.ema20 = ema20_ind.latest_value
        context.ema50 = ema50_ind.latest_value
        context.ema200 = ema200_ind.latest_value
        
        if context.ema20 is None or context.ema50 is None or context.ema200 is None:
            return RuleResult.reject("ema_unavailable")

        side = None
        side_hits = ()
        if context.ema20 > context.ema50 > context.ema200:
            side = "BUY"
        elif context.ema20 < context.ema50 < context.ema200:
            side = "SELL"
        else:
            side, side_hits = infer_trade_side(
                ema20=context.ema20,
                ema50=context.ema50,
                ema200=context.ema200,
                regime_result=context.regime_result,
                adx_trend_threshold=context.adx_trend_threshold,
                highs=highs,
                lows=lows,
                closes=closes,
            )
        
        if side is None:
            return RuleResult.reject("ema_misalignment")
            
        allowed_dirs = settings.advisor_allowed_directions
        if side not in allowed_dirs:
            return RuleResult.reject(f"direction_blocked_{side}")
            
        if side == "SELL":
            ok_sell, sell_reason = validate_sell_regime(
                side,
                adx=context.regime_result.adx,
                regime=context.regime_result.regime,
                timeframe=context.candle_list.timeframe,
            )
            if not ok_sell:
                return RuleResult.reject(sell_reason)

            pd = context.regime_result.plus_di
            md = context.regime_result.minus_di
            min_di_spread = settings.ADVISOR_SELL_MIN_DI_SPREAD
            if context.candle_list.timeframe in ("4h", "1d"):
                min_di_spread = max(min_di_spread, settings.ADVISOR_SWING_SELL_MIN_DI_SPREAD)
            if pd is not None and md is not None:
                if (md - pd) < min_di_spread:
                    return RuleResult.reject(f"sell_di_spread_{md - pd:.1f}")
                    
        context.side = side
        context.side_hits = side_hits
        context.confluence_hits.extend(list(side_hits))
        context.confluence_hits.append("ema_alignment")
        
        swing_ok = _swing_structure_ok(highs, lows, side=side)
        context.swing_ok = swing_ok
        if not swing_ok and _swing_structure_required(context.regime_result.adx, context.candle_list.timeframe):
            return RuleResult.reject("swing_structure_failed")
            
        if swing_ok:
            context.confluence_hits.append("swing_structure")
            
        return RuleResult.ok()
