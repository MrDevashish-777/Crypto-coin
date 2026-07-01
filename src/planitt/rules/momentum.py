import math
from config.settings import settings
from src.planitt.rules.base import ConfluenceRule, RuleContext, RuleResult
from src.indicators.rsi import RSI
from src.indicators.macd import MACD
from src.indicators.atr import ATR
from src.indicators.nadaraya_watson import NadarayaWatsonEnvelope
from src.planitt.crypto_futures_analysis import crypto_momentum_hit, relative_volume_spike

def _volume_ratio(volumes: list[float], lookback: int) -> float:
    if len(volumes) < lookback + 1:
        return 1.0
    prev = volumes[-(lookback + 1) : -1]
    avg = sum(prev) / max(len(prev), 1)
    if avg <= 0:
        return 1.0
    return volumes[-1] / avg

def _choppiness_index(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    tr_values: list[float] = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        tr_values.append(tr)
    tr_sum = sum(tr_values[-period:])
    high_n = max(highs[-period:])
    low_n = min(lows[-period:])
    if high_n <= low_n:
        return 50.0
    return 100 * math.log10(tr_sum / (high_n - low_n)) / math.log10(period)

def _is_squeeze(closes: list[float], highs: list[float], lows: list[float], period: int = 20) -> bool:
    if len(closes) < period + 2:
        return False
    subset = closes[-period:]
    mean = sum(subset) / period
    variance = sum((x - mean) ** 2 for x in subset) / period
    std_dev = variance ** 0.5
    bb_upper = mean + (2 * std_dev)
    bb_lower = mean - (2 * std_dev)
    tr_values = []
    for i in range(len(closes) - period + 1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        tr_values.append(tr)
    atr = sum(tr_values) / max(1, len(tr_values))
    kc_upper = mean + (1.5 * atr)
    kc_lower = mean - (1.5 * atr)
    return bb_upper <= kc_upper and bb_lower >= kc_lower

def _momentum_confirmed(
    side: str,
    rsi: float,
    prev_rsi: float,
    macd_hist: float,
    macd_hist_prev: float,
    *,
    adx: float | None = None,
) -> bool:
    strong = adx is not None and adx >= settings.PLANITT_ADX_TREND_THRESHOLD + 3
    if side == "BUY":
        if strong:
            return 35 <= rsi <= 70 and macd_hist > 0 and (rsi >= prev_rsi or macd_hist >= macd_hist_prev)
        return 40 <= rsi <= 65 and rsi >= prev_rsi and macd_hist > 0 and macd_hist >= macd_hist_prev
    if strong:
        return 30 <= rsi <= 65 and macd_hist < 0 and (rsi <= prev_rsi or macd_hist <= macd_hist_prev)
    return 35 <= rsi <= 60 and rsi <= prev_rsi and macd_hist < 0 and macd_hist <= macd_hist_prev

class MomentumRule(ConfluenceRule):
    """
    Evaluates RSI, MACD, Volume, Volatility, and Envelopes.
    Updates context with these values and associated confluence hits.
    """
    def evaluate(self, context: RuleContext) -> RuleResult:
        closes = context.candle_list.closes
        highs = context.candle_list.highs
        lows = context.candle_list.lows
        volumes = context.candle_list.volumes

        rsi_ind = RSI(period=14)
        rsi_ind.calculate(closes)
        context.rsi = rsi_ind.latest_value
        context.prev_rsi = rsi_ind.previous_value
        if context.rsi is None or context.prev_rsi is None:
            return RuleResult.reject("rsi_unavailable")

        macd_ind = MACD()
        macd_ind.calculate(closes)
        hist = macd_ind.histogram
        if len(hist) < 2:
            return RuleResult.reject("macd_unavailable")
        context.macd_hist = hist[-1]
        context.macd_hist_prev = hist[-2]

        atr_ind = ATR(period=14)
        atr_values = atr_ind.calculate_from_ohlc(highs, lows, closes)
        if not atr_values:
            return RuleResult.reject("atr_unavailable")
        context.atr = float(atr_values[-1])

        context.volume_ratio = _volume_ratio(volumes, lookback=settings.PLANITT_VOLUME_LOOKBACK)
        context.current_volume = float(volumes[-1])
        context.price = float(closes[-1])

        if settings.ENABLE_NWE and len(closes) >= 50:
            context.nwe_snap = NadarayaWatsonEnvelope(
                bandwidth=settings.NWE_BANDWIDTH,
                multiplier=settings.NWE_MULTIPLIER,
                lookback=min(settings.NWE_LOOKBACK, len(closes)),
            ).snapshot(closes, band_touch_pct=settings.NWE_BAND_TOUCH_PCT)

        strict_momentum = _momentum_confirmed(
            context.side,
            float(context.rsi),
            float(context.prev_rsi),
            float(context.macd_hist),
            float(context.macd_hist_prev),
            adx=context.regime_result.adx,
        )
        momentum_tag = crypto_momentum_hit(
            context.side,
            float(context.rsi),
            float(context.prev_rsi),
            float(context.macd_hist),
            float(context.macd_hist_prev),
            adx=context.regime_result.adx,
            plus_di=context.regime_result.plus_di,
            minus_di=context.regime_result.minus_di,
            strict_confirmed=strict_momentum,
        )
        if momentum_tag:
            context.confluence_hits.append(momentum_tag)

        if context.volume_ratio >= context.volume_multiplier or relative_volume_spike(volumes):
            context.confluence_hits.append("volume_spike")
            
        choppiness = _choppiness_index(highs, lows, closes)
        if choppiness < settings.PLANITT_CHOPPINESS_MAX:
            context.confluence_hits.append("low_choppiness")
            
        squeeze_on = _is_squeeze(closes, highs, lows)
        if squeeze_on:
            context.confluence_hits.append("squeeze_regime")

        if context.nwe_snap:
            if context.side == "BUY" and context.nwe_snap.bull_bounce:
                context.confluence_hits.append("nwe_lower_bounce")
            elif context.side == "SELL" and context.nwe_snap.bear_rejection:
                context.confluence_hits.append("nwe_upper_rejection")
            if context.side == "BUY" and context.nwe_snap.near_lower:
                context.confluence_hits.append("nwe_near_lower")
            elif context.side == "SELL" and context.nwe_snap.near_upper:
                context.confluence_hits.append("nwe_near_upper")

        return RuleResult.ok()
