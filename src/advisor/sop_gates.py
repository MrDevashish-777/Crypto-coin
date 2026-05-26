"""SOP §5–6 validation gates."""

from __future__ import annotations

from dataclasses import dataclass

from config.settings import settings

SOP_MIN_RR = 1.5
SOP_MIN_TP_SL_PCT = 2.5
SOP_ENTRY_WIDTH_MIN = 0.5
SOP_ENTRY_WIDTH_MAX = 1.5
SOP_LEVERAGED_SL_MIN = 18.0
SOP_LEVERAGED_SL_MAX = 22.0


@dataclass(frozen=True)
class SOPValidationResult:
    ok: bool
    reason: str | None = None


def validate_levels(
    *,
    direction: str,
    entry_low: float,
    entry_high: float,
    stop_loss: float,
    target: float,
    live_price: float,
    sl_pct: float,
    tp_pct: float,
    leverage: float,
    risk_reward: str,
    confidence: float,
) -> SOPValidationResult:
    """Hard reject if any SOP trading parameter is violated."""
    if confidence < settings.ADVISOR_MIN_CONFIDENCE:
        return SOPValidationResult(False, f"confidence_below_{settings.ADVISOR_MIN_CONFIDENCE}")

    low, high = sorted([entry_low, entry_high])
    entry_mid = (low + high) / 2.0
    width_pct = (high - low) / entry_mid * 100.0
    if width_pct < SOP_ENTRY_WIDTH_MIN or width_pct > SOP_ENTRY_WIDTH_MAX:
        return SOPValidationResult(False, f"entry_width_{width_pct:.2f}pct")

    if not (low <= live_price <= high):
        return SOPValidationResult(False, "price_outside_entry_range")

    if sl_pct < settings.SOP_MIN_SL_PCT - 0.01 or tp_pct < settings.SOP_MIN_SL_PCT - 0.01:
        return SOPValidationResult(False, f"tp_sl_pct_too_tight:sl={sl_pct} tp={tp_pct}")

    lev_sl = sl_pct * leverage
    if lev_sl < settings.SOP_LEVERAGED_SL_MIN - 0.5 or lev_sl > settings.SOP_LEVERAGED_SL_MAX + 0.5:
        return SOPValidationResult(False, f"leveraged_sl_{lev_sl:.1f}")

    expected_lev = 20.0 / sl_pct if sl_pct > 0 else 0
    if abs(leverage - expected_lev) > 1.0:
        return SOPValidationResult(False, "leverage_mismatch")

    try:
        rr_val = float(risk_reward.split(":", 1)[1])
    except (IndexError, ValueError):
        return SOPValidationResult(False, "invalid_rr_format")
    if rr_val < settings.SOP_MIN_RR:
        return SOPValidationResult(False, f"rr_below_{settings.SOP_MIN_RR}")

    risk = abs(entry_mid - stop_loss)
    reward = abs(target - entry_mid)
    if reward / max(risk, 1e-9) < settings.SOP_MIN_RR - 0.05:
        return SOPValidationResult(False, "actual_rr_too_low")

    if direction == "BUY":
        if not (stop_loss < low and target > high):
            return SOPValidationResult(False, "buy_level_order")
    else:
        if not (stop_loss > high and target < low):
            return SOPValidationResult(False, "sell_level_order")

    if leverage < 2.0:
        return SOPValidationResult(False, "leverage_below_2x")

    return SOPValidationResult(True)
