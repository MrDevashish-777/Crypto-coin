from config.settings import settings
from src.planitt.rules.base import ConfluenceRule, RuleContext, RuleResult
from src.planitt.crypto_futures_analysis import detect_liquidity_sweep_setup, detect_vwap_setup
from src.planitt.smc_setup import detect_fvg_ob_setup
from src.indicators.candlestick_patterns import detect_latest_candlestick_pattern
from src.planitt.indicator_votes import evaluate_indicator_votes

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

def _validate_mandatory_categories(hits: list[str], *, has_setup: bool) -> bool:
    # If it's a strong SMC/VWAP setup, it overrides basic indicator trend/momentum requirements
    is_smc_or_vwap = any(
        h in hits for h in (
            "smc_liquidity_sweep", "smc_sweep_reclaim", "smc_sweep_reject",
            "smc_fvg_ob_overlap", "vwap_reclaim", "vwap_reject"
        )
    )
    
    trend_ok = is_smc_or_vwap or ("ema_alignment" in hits and (
        "swing_structure" in hits
        or "supertrend_alignment" in hits
        or "di_trend_confirm" in hits
        or not settings.PLANITT_REQUIRE_SWING_STRUCTURE
        or "directional_ranging" in hits
        or "adx_ranging" in hits
    ))
    
    momentum_ok = is_smc_or_vwap or (
        "rsi_macd_confirmation" in hits
        or "macd_direction" in hits
        or "di_macd_momentum" in hits
    )
    
    location_ok = has_setup or any(
        h.startswith("key_level_reaction") or h.startswith("nwe_") for h in hits
    ) or "trend_continuation" in hits or is_smc_or_vwap
    quality_ok = any(
        h in hits
        for h in (
            "volume_spike",
            "low_choppiness",
            "squeeze_regime",
            "candlestick_confirmation",
            "nwe_lower_bounce",
            "nwe_upper_rejection",
            "smc_liquidity_sweep",
            "smc_sweep_reclaim",
            "smc_sweep_reject",
            "vwap_reclaim",
            "vwap_reject",
        )
    ) or any(h.startswith("candlestick_") for h in hits) or any(h.startswith("vote_") for h in hits)
    return trend_ok and momentum_ok and location_ok and quality_ok

class SetupsRule(ConfluenceRule):
    """
    Evaluates specific setups (pullback, breakout, sweeps, FVG).
    Validates mandatory categories and indicator votes.
    """
    def evaluate(self, context: RuleContext) -> RuleResult:
        closes = context.candle_list.closes
        highs = context.candle_list.highs
        lows = context.candle_list.lows
        volumes = context.candle_list.volumes
        opens = context.candle_list.opens
        price = context.price
        side = context.side

        lookback = 20
        prev_high = max(highs[-(lookback + 1) : -1]) if len(highs) > lookback + 1 else price
        prev_low = min(lows[-(lookback + 1) : -1]) if len(lows) > lookback + 1 else price

        pullback_touch = False
        breakout_break = False

        # SOP SMC Enforced: Disable basic pullbacks and breakouts
        pullback_touch = False
        breakout_break = False

        key_level = None
        breakout_level = None
        setup_type = None

        sweep_setup = detect_liquidity_sweep_setup(
            opens, highs, lows, closes, volumes, side=side, atr=context.atr
        )
        if sweep_setup is not None:
            context.confluence_hits.extend(sweep_setup.hits)
            setup_type = "liquidity_sweep"
            key_level = sweep_setup.key_level
        else:
            vwap_setup = detect_vwap_setup(highs, lows, closes, volumes, side=side)
            if vwap_setup is not None:
                context.confluence_hits.extend(vwap_setup.hits)
                setup_type = "vwap_reclaim"
                key_level = vwap_setup.key_level
            else:
                smc_setup = detect_fvg_ob_setup(
                    opens, highs, lows, closes, volumes, price=price, atr=context.atr, side=side
                )
                if smc_setup is not None:
                    context.confluence_hits.extend(smc_setup.hits)
                    setup_type = "fvg_ob_retest"
                    key_level = smc_setup.key_level
                else:
                    return RuleResult.reject("no_valid_setup")

        context.key_level = key_level
        context.breakout_level = breakout_level
        context.setup_type = setup_type

        effective_min_hits = context.min_confluence_hits
        adx_val = context.regime_result.adx or 0.0
        if adx_val >= context.adx_trend_threshold + 2:
            effective_min_hits = min(settings.PLANITT_MIN_HITS_STRONG_ADX, context.min_confluence_hits)

        if len(context.confluence_hits) < effective_min_hits or setup_type is None:
            return RuleResult.reject(f"confluence_hits_too_low:{len(context.confluence_hits)}")

        if settings.ENABLE_CANDLESTICK_PATTERNS:
            pattern = detect_latest_candlestick_pattern(
                opens=opens, highs=highs, lows=lows, closes=closes, volumes=volumes
            )
            if pattern and pattern["strength"] >= settings.PATTERN_MIN_STRENGTH:
                context.pattern_name = pattern["pattern_name"]
                context.pattern_bias = pattern["bias"]
                context.pattern_strength = float(pattern["strength"])
                context.pattern_confirmed = bool(pattern["confirmation"])
                
                side_is_bull = side == "BUY"
                opposing = (side_is_bull and context.pattern_bias == "bear") or (
                    (not side_is_bull) and context.pattern_bias == "bull"
                )
                if opposing and context.pattern_strength >= settings.PLANITT_OPPOSING_PATTERN_VETO_STRENGTH:
                    return RuleResult.reject(f"opposing_pattern:{context.pattern_name}")
                
                at_level = True
                if settings.PATTERN_AT_LEVEL_REQUIRED:
                    tol = context.touch_tolerance_pct
                    at_level = any(
                        abs(price - lvl) / lvl <= tol
                        for lvl in (key_level, float(context.ema50))
                        if lvl
                    )
                if at_level and (
                    (side_is_bull and context.pattern_bias == "bull")
                    or ((not side_is_bull) and context.pattern_bias == "bear")
                ):
                    context.confluence_hits.append(f"candlestick_{context.pattern_name.lower()}")
                    if context.pattern_confirmed:
                        context.confluence_hits.append("candlestick_confirmation")

        if settings.PLANITT_REQUIRE_MANDATORY_CATEGORIES and not _validate_mandatory_categories(
            context.confluence_hits, has_setup=setup_type is not None
        ):
            return RuleResult.reject("mandatory_categories_failed")

        vote_result = evaluate_indicator_votes(
            context.candle_list,
            expected_side=side,
            key_level=float(key_level),
            ema50=float(context.ema50),
            timeframe=context.candle_list.timeframe,
            adx=context.regime_result.adx,
            plus_di=context.regime_result.plus_di,
            minus_di=context.regime_result.minus_di,
        )
        if vote_result.reject_reason:
            return RuleResult.reject(vote_result.reject_reason)
            
        context.agreeing_sources = vote_result.agreeing_sources
        context.pre_confidence = vote_result.pre_confidence
        context.vote_hits = list(vote_result.confluence_hits)

        return RuleResult.ok()
