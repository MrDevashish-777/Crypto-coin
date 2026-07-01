"""FVG + Order Block retest setups for larger SMC-aligned moves."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from config.settings import settings
from src.indicators.smc import SMC

SignalSide = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class FvgObSetup:
    side: SignalSide
    key_level: float
    ob_zone: tuple[float, float]
    fvg_zone: Optional[tuple[float, float]]
    big_move: bool
    hits: tuple[str, ...]


def _in_zone(price: float, bottom: float, top: float, atr: float) -> bool:
    pad = atr * settings.ADVISOR_SMC_ZONE_ATR_PAD
    return (bottom - pad) <= price <= (top + pad)


def detect_fvg_ob_setup(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float],
    *,
    price: float,
    atr: float,
    side: SignalSide,
) -> Optional[FvgObSetup]:
    """
    Price retesting a fresh OB with optional overlapping FVG — institutional entry zone.
    big_move=True when OB+FVG overlap (higher R:R target to opposing liquidity).
    """
    if not settings.ADVISOR_SMC_FVG_OB_ENABLED:
        return None

    data = SMC().calculate_from_ohlc(opens, highs, lows, closes, volumes)
    lookback = settings.ADVISOR_SMC_SETUP_LOOKBACK_BARS
    recent = len(closes) - lookback

    obs = [
        ob
        for ob in data.get("order_blocks", [])
        if ob.get("active") and ob.get("index", 0) >= recent
    ]
    fvgs = [
        f
        for f in data.get("fvgs", [])
        if f.get("active") and f.get("index", 0) >= recent
    ]

    want = "bullish" if side == "BUY" else "bearish"
    hits: list[str] = []
    matched_ob: dict | None = None
    matched_fvg: dict | None = None

    for ob in reversed(obs):
        if ob["type"] != want:
            continue
        if _in_zone(price, ob["bottom"], ob["top"], atr):
            matched_ob = ob
            hits.append("smc_order_block_retest")
            break

    if matched_ob is None:
        return None

    for fvg in reversed(fvgs):
        if fvg["type"] != want:
            continue
        if _in_zone(price, fvg["bottom"], fvg["top"], atr):
            matched_fvg = fvg
            hits.append("smc_fvg_retest")
            break

    ob_lo, ob_hi = matched_ob["bottom"], matched_ob["top"]
    fvg_zone: Optional[tuple[float, float]] = None
    big_move = False
    if matched_fvg is not None:
        fvg_lo, fvg_hi = matched_fvg["bottom"], matched_fvg["top"]
        fvg_zone = (fvg_lo, fvg_hi)
        overlap = max(ob_lo, fvg_lo) <= min(ob_hi, fvg_hi)
        if overlap:
            hits.append("smc_fvg_ob_overlap")
            big_move = True

    key_level = (ob_lo + ob_hi) / 2.0
    return FvgObSetup(
        side=side,
        key_level=key_level,
        ob_zone=(ob_lo, ob_hi),
        fvg_zone=fvg_zone,
        big_move=big_move,
        hits=tuple(hits),
    )


def opposing_liquidity_tp(
    smc_data: dict,
    *,
    entry: float,
    side: SignalSide,
    min_rr: float,
    sl: float,
) -> Optional[float]:
    """Target next opposing OB/FVG (liquidity pool) for extended R:R."""
    if not settings.ADVISOR_SMC_LIQUIDITY_TP_ENABLED:
        return None

    risk = abs(entry - sl)
    if risk <= 0:
        return None

    candidates: list[float] = []
    if side == "BUY":
        for ob in smc_data.get("order_blocks", []):
            if ob.get("type") == "bearish" and ob.get("bottom", 0) > entry:
                candidates.append(float(ob["bottom"]))
        for fvg in smc_data.get("fvgs", []):
            if fvg.get("type") == "bearish" and fvg.get("bottom", 0) > entry:
                candidates.append(float(fvg["bottom"]))
        if not candidates:
            return None
        tp = min(candidates)
    else:
        for ob in smc_data.get("order_blocks", []):
            if ob.get("type") == "bullish" and ob.get("top", 0) < entry:
                candidates.append(float(ob["top"]))
        for fvg in smc_data.get("fvgs", []):
            if fvg.get("type") == "bullish" and fvg.get("top", 0) < entry:
                candidates.append(float(fvg["top"]))
        if not candidates:
            return None
        tp = max(candidates)

    reward = abs(tp - entry)
    if reward / risk < min_rr:
        return None
    return tp
