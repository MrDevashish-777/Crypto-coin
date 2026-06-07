"""SOP-compliant single-TP target computation with structure-aware RiskManager."""

from __future__ import annotations

from typing import Literal, Optional

from config.settings import settings
from src.data.models import CandleList
from src.indicators.fibonacci import FibonacciLevels
from src.indicators.nadaraya_watson import NadarayaWatsonEnvelope
from src.indicators.pivot_points import PivotPoints
from src.indicators.smc import SMC
from src.planitt.confluence import ConfluenceFeatures, find_pivots
from src.risk.risk_manager import RiskManager
from src.signals.market_regime import MarketRegime, MarketRegimeDetector

Direction = Literal["long", "short"]


def _sop_constants() -> dict[str, float]:
    return {
        "min_sl_pct": settings.SOP_MIN_SL_PCT,
        "max_sl_pct": settings.SOP_MAX_SL_PCT,
        "min_rr": settings.SOP_MIN_RR,
        "lev_sl_min": settings.SOP_LEVERAGED_SL_MIN,
        "lev_sl_max": settings.SOP_LEVERAGED_SL_MAX,
    }


def _entry_band(price: float, atr: float, *, setup_type: str, key_level: float, direction: Direction) -> tuple[float, float]:
    """Entry range 0.5–1.5% width centered near current structure."""
    mid = price
    if setup_type == "trend_pullback":
        mid = (price + key_level) / 2.0 if key_level else price
    elif setup_type == "volume_breakout":
        mid = key_level if key_level else price

    half_pct = 0.005
    half = max(mid * half_pct, atr * 0.04)
    width_pct = (2 * half) / mid * 100.0
    if width_pct < 0.5:
        half = mid * 0.0025
    elif width_pct > 1.5:
        half = mid * 0.0075

    if direction == "long":
        return mid - half, mid + half
    return mid - half, mid + half


def _swing_stop_buffer(
    highs: list[float],
    lows: list[float],
    *,
    side: str,
    atr: float,
) -> Optional[float]:
    """Return swing-based SL price beyond recent pivot."""
    window = min(80, len(highs))
    piv_lows = find_pivots(lows[-window:], is_high=False)
    piv_highs = find_pivots(highs[-window:], is_high=True)
    buffer = atr * 0.25
    if side == "BUY" and piv_lows:
        return piv_lows[-1][1] - buffer
    if side == "SELL" and piv_highs:
        return piv_highs[-1][1] + buffer
    return None


def _has_nwe_confluence(features: ConfluenceFeatures) -> bool:
    hits = features.confluence_hits
    return any(
        h in hits
        for h in ("nwe_lower_bounce", "nwe_upper_rejection")
    ) or any(h == "vote_nwe" for h in hits)


def _use_nwe_tp_sl(features: ConfluenceFeatures, *, high_prob: bool) -> bool:
    if not settings.ENABLE_NWE or not settings.NWE_TP_SL_ENABLED:
        return False
    if high_prob:
        return True
    return (
        features.pre_confidence >= settings.NWE_TP_SL_MIN_CONFIDENCE
        and _has_nwe_confluence(features)
    )


def _nwe_tp_sl(
    *,
    side: str,
    entry_mid: float,
    entry_low: float,
    entry_high: float,
    closes: list[float],
    atr: float,
    min_rr: float,
) -> Optional[tuple[float, float]]:
    """
    Envelope-based targets: long TP at upper band, SL below lower; short mirrored.
    """
    nwe = NadarayaWatsonEnvelope(
        bandwidth=settings.NWE_BANDWIDTH,
        multiplier=settings.NWE_MULTIPLIER,
        lookback=min(settings.NWE_LOOKBACK, len(closes)),
    )
    snap = nwe.snapshot(closes, band_touch_pct=settings.NWE_BAND_TOUCH_PCT)
    if snap is None:
        return None

    buffer = max(
        atr * settings.NWE_SL_BUFFER_ATR_MULT,
        snap.mae * 0.08,
        entry_mid * 0.001,
    )

    if side == "BUY":
        stop_loss = snap.lower - buffer
        target = snap.upper
        if stop_loss >= entry_low or target <= entry_high:
            return None
        risk = entry_mid - stop_loss
        if risk <= 0:
            return None
        reward = target - entry_mid
        if reward / risk < min_rr:
            target = entry_mid + risk * min_rr
        if target <= entry_high:
            return None
        return target, stop_loss

    stop_loss = snap.upper + buffer
    target = snap.lower
    if stop_loss <= entry_high or target >= entry_low:
        return None
    risk = stop_loss - entry_mid
    if risk <= 0:
        return None
    reward = entry_mid - target
    if reward / risk < min_rr:
        target = entry_mid - risk * min_rr
    if target >= entry_low:
        return None
    return target, stop_loss


def _regime_label(candle_list: Optional[CandleList]) -> str:
    if candle_list is None:
        return "trending"
    result = MarketRegimeDetector().detect(candle_list)
    if result.regime in (MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN):
        return "trending"
    if result.regime == MarketRegime.VOLATILE:
        return "volatile"
    return "ranging"


def compute_advisor_levels(
    features: ConfluenceFeatures,
    *,
    candle_list: Optional[CandleList] = None,
) -> dict[str, float | str | list[float]]:
    """
    Compute entry band, single SL/TP, and SOP percentages using adaptive risk + structure.
    """
    sop = _sop_constants()
    side = features.side
    direction: Direction = "long" if side == "BUY" else "short"
    price = float(features.price)
    atr = max(float(features.atr or 0.0), price * 0.0008)
    horizon = "swing" if features.timeframe in ("4h", "1d") else "intraday"

    entry_low, entry_high = _entry_band(
        price,
        atr,
        setup_type=features.setup_type,
        key_level=float(features.key_level),
        direction=direction,
    )
    entry_mid = (entry_low + entry_high) / 2.0

    high_prob = (
        features.pre_confidence >= settings.SOP_HIGH_CONF_THRESHOLD
        and features.agreeing_sources >= settings.SOP_HIGH_CONF_MIN_SOURCES
    )
    regime = _regime_label(candle_list)
    risk_manager = RiskManager(min_risk_reward=sop["min_rr"])

    fib_data = None
    pivot_levels = None
    smc_data = None
    if candle_list is not None:
        highs, lows, closes = candle_list.highs, candle_list.lows, candle_list.closes
        opens, volumes = candle_list.opens, candle_list.volumes
        try:
            fib_data = FibonacciLevels(swing_lookback=50).calculate_from_ohlc(highs, lows, closes)
        except Exception:
            pass
        try:
            if len(closes) >= 2:
                pivot_levels = PivotPoints().calculate_classic(
                    prev_high=max(highs[-2:]),
                    prev_low=min(lows[-2:]),
                    prev_close=closes[-2],
                )
        except Exception:
            pass
        try:
            smc_data = SMC().calculate_from_ohlc(opens, highs, lows, closes, volumes)
        except Exception:
            pass

    target, stop_loss, _meta = risk_manager.calculate_adaptive_tp_sl(
        entry_price=entry_mid,
        atr=atr,
        direction=direction,
        regime=regime,
        fib_levels=fib_data,
        pivot_levels=pivot_levels,
        smc_data=smc_data,
        high_probability=high_prob,
    )

    tp_sl_method = "atr_structure"
    use_nwe = _use_nwe_tp_sl(features, high_prob=high_prob)
    if use_nwe and candle_list is not None and len(candle_list.closes) >= 50:
        nwe_levels = _nwe_tp_sl(
            side=side,
            entry_mid=entry_mid,
            entry_low=entry_low,
            entry_high=entry_high,
            closes=candle_list.closes,
            atr=atr,
            min_rr=settings.SOP_HIGH_CONF_MIN_RR if high_prob else sop["min_rr"],
        )
        if nwe_levels is not None:
            target, stop_loss = nwe_levels
            tp_sl_method = "nwe_envelope"

    if candle_list is not None and tp_sl_method != "nwe_envelope":
        swing_sl = _swing_stop_buffer(
            candle_list.highs,
            candle_list.lows,
            side=side,
            atr=atr,
        )
        if swing_sl is not None:
            if side == "BUY" and swing_sl < stop_loss:
                stop_loss = swing_sl
            elif side == "SELL" and swing_sl > stop_loss:
                stop_loss = swing_sl

    sl_pct = abs(entry_mid - stop_loss) / entry_mid * 100.0
    tp_pct = abs(target - entry_mid) / entry_mid * 100.0

    min_rr = settings.SOP_HIGH_CONF_MIN_RR if high_prob else sop["min_rr"]
    risk = abs(entry_mid - stop_loss)
    reward = abs(target - entry_mid)
    rr = reward / max(risk, 1e-9)
    if rr < min_rr:
        if side == "BUY":
            target = entry_mid + risk * min_rr
        else:
            target = entry_mid - risk * min_rr
        tp_pct = abs(target - entry_mid) / entry_mid * 100.0
        rr = min_rr

    if sl_pct < sop["min_sl_pct"]:
        sl_pct = sop["min_sl_pct"]
        if side == "BUY":
            stop_loss = entry_mid * (1 - sl_pct / 100.0)
            target = max(target, entry_mid + abs(entry_mid - stop_loss) * min_rr)
        else:
            stop_loss = entry_mid * (1 + sl_pct / 100.0)
            target = min(target, entry_mid - abs(stop_loss - entry_mid) * min_rr)

    if sl_pct > sop["max_sl_pct"]:
        sl_pct = sop["max_sl_pct"]
        if side == "BUY":
            stop_loss = entry_mid * (1 - sl_pct / 100.0)
            target = max(target, entry_mid + abs(entry_mid - stop_loss) * min_rr)
        else:
            stop_loss = entry_mid * (1 + sl_pct / 100.0)
            target = min(target, entry_mid - abs(stop_loss - entry_mid) * min_rr)

    leverage = 20.0 / sl_pct
    leveraged_sl = sl_pct * leverage
    if leveraged_sl < sop["lev_sl_min"]:
        sl_pct = sop["lev_sl_min"] / leverage if leverage else sl_pct
        leverage = 20.0 / sl_pct
    elif leveraged_sl > sop["lev_sl_max"]:
        sl_pct = sop["lev_sl_max"] / leverage if leverage else sl_pct
        leverage = 20.0 / sl_pct

    if side == "BUY":
        if stop_loss >= entry_low:
            stop_loss = entry_mid * (1 - sl_pct / 100.0)
        if target <= entry_high:
            target = entry_mid + abs(entry_mid - stop_loss) * min_rr
    else:
        if stop_loss <= entry_high:
            stop_loss = entry_mid * (1 + sl_pct / 100.0)
        if target >= entry_low:
            target = entry_mid - abs(stop_loss - entry_mid) * min_rr
            
    if target <= 0:
        target = entry_mid * 0.01

    tp_pct = abs(target - entry_mid) / entry_mid * 100.0
    risk = abs(entry_mid - stop_loss)
    reward = abs(target - entry_mid)
    rr = reward / max(risk, 1e-9)

    chart_indicators: list[str] = []
    if tp_sl_method == "nwe_envelope":
        chart_indicators.append("NWE")
    if any(h.startswith("vote_supertrend") or h.startswith("vote_ichimoku") for h in features.confluence_hits):
        chart_indicators.append("Supertrend")
    if "ema_alignment" in features.confluence_hits or "swing_structure" in features.confluence_hits:
        chart_indicators.append("EMA 50")
    if "rsi_macd_confirmation" in features.confluence_hits:
        chart_indicators.append("RSI 14")
    elif "volume_spike" in features.confluence_hits:
        chart_indicators.append("Volume")
    if len(chart_indicators) < 2 and features.adx is not None:
        chart_indicators.append("ADX 14")
    chart_indicators = chart_indicators[:2]

    return {
        "entry_low": round(entry_low, 8),
        "entry_high": round(entry_high, 8),
        "stop_loss": round(stop_loss, 8),
        "target": round(target, 8),
        "sl_pct": round(sl_pct, 4),
        "tp_pct": round(tp_pct, 4),
        "leverage": round(leverage, 1),
        "risk_reward": f"1:{rr:.1f}",
        "chart_indicators": chart_indicators,
        "tp_sl_method": tp_sl_method,
    }
