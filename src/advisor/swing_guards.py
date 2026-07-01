"""Extra validation for 4h / 1d swing signals — fixes historical −6.3R on 4h."""

from __future__ import annotations

from config.settings import settings
from src.advisor.validity import infer_trade_horizon
from src.planitt.confluence import ConfluenceFeatures

SWING_TIMEFRAMES = frozenset({"4h", "1d"})


def is_swing_timeframe(timeframe: str) -> bool:
    return timeframe in SWING_TIMEFRAMES or infer_trade_horizon(timeframe) == "swing"


def validate_swing_signal(
    features: ConfluenceFeatures,
    timeframe: str,
    *,
    mtf_score: float,
    tier: str,
) -> tuple[bool, str | None]:
    """Stricter swing-only checks beyond segment gates."""
    if not is_swing_timeframe(timeframe):
        return True, None

    hits = features.confluence_hits
    structure_hits = (
        "swing_structure",
        "smc_order_block_retest",
        "smc_fvg_retest",
        "smc_fvg_ob_overlap",
        "key_level_reaction_pullback",
        "key_level_reaction_breakout",
    )
    if settings.ADVISOR_SWING_REQUIRE_STRUCTURE:
        if not any(h in hits for h in structure_hits):
            return False, "swing_no_structure_confluence"

    min_mtf = (
        settings.ADVISOR_1D_MIN_MTF_SCORE
        if timeframe == "1d"
        else settings.ADVISOR_4H_MIN_MTF_SCORE
    )
    if mtf_score < min_mtf:
        return False, f"swing_mtf_below_{mtf_score:.2f}"

    if timeframe == "1d":
        if tier != "A":
            return False, f"swing_1d_requires_tier_a_{tier}"
        if features.pre_confidence < settings.ADVISOR_1D_MIN_CONFIDENCE:
            return False, f"swing_1d_conf_{features.pre_confidence:.2f}"

    if features.side == "SELL" and timeframe in SWING_TIMEFRAMES:
        if features.adx is not None and features.adx < _swing_sell_min_adx(timeframe):
            return False, f"swing_sell_adx_{features.adx:.1f}"

    return True, None


def _swing_sell_min_adx(timeframe: str) -> float:
    if timeframe == "1d":
        return settings.ADVISOR_1D_SELL_MIN_ADX
    if timeframe == "4h":
        return settings.ADVISOR_4H_SELL_MIN_ADX
    return settings.ADVISOR_SELL_MIN_ADX


def swing_min_rr(timeframe: str) -> float:
    if is_swing_timeframe(timeframe):
        return settings.SOP_SWING_MIN_RR
    return settings.SOP_MIN_RR
