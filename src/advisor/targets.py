"""SOP-compliant single-TP target computation."""

from __future__ import annotations

from typing import Literal

from config.settings import settings
from src.planitt.confluence import ConfluenceFeatures

Direction = Literal["long", "short"]

SOP_MIN_SL_PCT = 2.5
SOP_MAX_SL_PCT = 4.0
SOP_MIN_RR = 1.5
SOP_LEVERAGED_SL_MIN = 18.0
SOP_LEVERAGED_SL_MAX = 22.0


def _entry_band(price: float, atr: float, *, setup_type: str, key_level: float, direction: Direction) -> tuple[float, float]:
    """Entry range 0.5–1.5% width centered near current structure."""
    mid = price
    if setup_type == "trend_pullback":
        mid = (price + key_level) / 2.0 if key_level else price
    elif setup_type == "volume_breakout":
        mid = key_level if key_level else price

    half_pct = 0.005  # 0.5% half → 1% total; tune toward SOP center
    half = max(mid * half_pct, atr * 0.04)
    width_pct = (2 * half) / mid * 100.0
    if width_pct < 0.5:
        half = mid * 0.0025
    elif width_pct > 1.5:
        half = mid * 0.0075

    if direction == "long":
        return mid - half, mid + half
    return mid - half, mid + half


def compute_advisor_levels(features: ConfluenceFeatures) -> dict[str, float | str | list[float]]:
    """
    Compute entry band, single SL/TP, and SOP percentages.

    SL% chosen so leveraged SL is 18–22% (leverage = 20/sl_pct).
    """
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

    atr_sl_mult = 1.2 if horizon == "intraday" else 1.6
    atr_tp_mult = 2.0 if horizon == "intraday" else 2.8

    sl_distance = max(atr * atr_sl_mult, entry_mid * (SOP_MIN_SL_PCT / 100.0))
    tp_distance = max(atr * atr_tp_mult, sl_distance * SOP_MIN_RR)

    if side == "BUY":
        stop_loss = entry_low - sl_distance
        target = entry_high + tp_distance
    else:
        stop_loss = entry_high + sl_distance
        target = entry_low - tp_distance

    sl_pct = abs(entry_mid - stop_loss) / entry_mid * 100.0
    tp_pct = abs(target - entry_mid) / entry_mid * 100.0

    if sl_pct < SOP_MIN_SL_PCT:
        scale = SOP_MIN_SL_PCT / max(sl_pct, 1e-9)
        sl_pct = SOP_MIN_SL_PCT
        if side == "BUY":
            stop_loss = entry_mid - (entry_mid - stop_loss) * scale
            target = entry_mid + (target - entry_mid) * scale
        else:
            stop_loss = entry_mid + (stop_loss - entry_mid) * scale
            target = entry_mid - (entry_mid - target) * scale
        tp_pct = abs(target - entry_mid) / entry_mid * 100.0

    if sl_pct > SOP_MAX_SL_PCT:
        sl_pct = SOP_MAX_SL_PCT
        if side == "BUY":
            stop_loss = entry_mid * (1 - sl_pct / 100.0)
        else:
            stop_loss = entry_mid * (1 + sl_pct / 100.0)

    leverage = 20.0 / sl_pct
    leveraged_sl = sl_pct * leverage
    if leveraged_sl < SOP_LEVERAGED_SL_MIN:
        sl_pct = SOP_LEVERAGED_SL_MIN / leverage if leverage else sl_pct
        leverage = 20.0 / sl_pct
    elif leveraged_sl > SOP_LEVERAGED_SL_MAX:
        sl_pct = SOP_LEVERAGED_SL_MAX / leverage if leverage else sl_pct
        leverage = 20.0 / sl_pct

    risk = abs(entry_mid - stop_loss)
    reward = abs(target - entry_mid)
    rr = reward / max(risk, 1e-9)
    if rr < SOP_MIN_RR:
        if side == "BUY":
            target = entry_mid + risk * SOP_MIN_RR
        else:
            target = entry_mid - risk * SOP_MIN_RR
        tp_pct = abs(target - entry_mid) / entry_mid * 100.0
        rr = SOP_MIN_RR

    chart_indicators: list[str] = []
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
    }
