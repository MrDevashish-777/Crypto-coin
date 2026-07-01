"""Crypto perpetual futures analysis — setups and side inference futures markets respect."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from config.settings import settings
from src.indicators.smc import SMC
from src.indicators.supertrend import Supertrend
from src.indicators.vwap import VWAP
from src.signals.market_regime import MarketRegime, RegimeResult

SignalSide = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class LiquiditySweepSetup:
    side: SignalSide
    key_level: float
    hits: tuple[str, ...]


@dataclass(frozen=True)
class VwapSetup:
    side: SignalSide
    key_level: float
    hits: tuple[str, ...]


def infer_trade_side(
    *,
    ema20: float,
    ema50: float,
    ema200: float,
    regime_result: RegimeResult,
    adx_trend_threshold: float,
    highs: list[float],
    lows: list[float],
    closes: list[float],
) -> tuple[Optional[SignalSide], tuple[str, ...]]:
    """
    Infer trade direction for crypto futures.

    Perfect EMA stacks are rare on 15m pullbacks; futures respect DI trend,
    Supertrend, and VWAP/EMA50 reclaim more than spot-style triple EMA stacks.
    """
    extra_hits: list[str] = []
    price = closes[-1]

    if ema20 > ema50 > ema200:
        return "BUY", tuple(extra_hits)
    if ema20 < ema50 < ema200:
        return "SELL", tuple(extra_hits)

    if not settings.PLANITT_RELAX_SIDE_FROM_REGIME:
        return None, tuple(extra_hits)

    adx = regime_result.adx
    adx_ok = adx is not None and adx >= adx_trend_threshold
    pd = regime_result.plus_di
    md = regime_result.minus_di
    di_bull = pd is not None and md is not None and pd > md
    di_bear = pd is not None and md is not None and md > pd
    di_spread = abs(pd - md) if pd is not None and md is not None else 0.0

    st = Supertrend(atr_period=10, multiplier=3.0)
    st.calculate_from_ohlc(highs, lows, closes)
    st_trend = st.get_current().get("trend")

    if settings.PLANITT_CRYPTO_FUTURES_ANALYSIS:
        if st_trend == 1:
            extra_hits.append("supertrend_alignment")
        elif st_trend == -1:
            extra_hits.append("supertrend_alignment")

        if di_spread >= settings.PLANITT_RANGING_MIN_DI_SPREAD and adx_ok:
            extra_hits.append("di_trend_confirm")
            if di_bull and st_trend == 1 and price >= ema50 * 0.998:
                return "BUY", tuple(dict.fromkeys(extra_hits))
            if di_bear and st_trend == -1 and price <= ema50 * 1.002:
                return "SELL", tuple(dict.fromkeys(extra_hits))
            if di_bull and price > ema200 and st_trend == 1:
                return "BUY", tuple(dict.fromkeys(extra_hits))
            if di_bear and price < ema200 and st_trend == -1:
                return "SELL", tuple(dict.fromkeys(extra_hits))

    if adx_ok and regime_result.regime == MarketRegime.TRENDING_UP and di_bull:
        return "BUY", tuple(extra_hits)
    if adx_ok and regime_result.regime == MarketRegime.TRENDING_DOWN and di_bear:
        return "SELL", tuple(extra_hits)
    if adx_ok and regime_result.regime == MarketRegime.VOLATILE and settings.PLANITT_ALLOW_VOLATILE_THROUGH_GATES:
        if di_bull:
            return "BUY", tuple(extra_hits)
        if di_bear and not settings.ADVISOR_BLOCK_VOLATILE_SELL:
            return "SELL", tuple(extra_hits)
    if adx_ok and regime_result.regime == MarketRegime.RANGING and di_spread >= settings.PLANITT_RANGING_MIN_DI_SPREAD:
        if di_bull and price > ema50:
            return "BUY", tuple(extra_hits)
        if di_bear and price < ema50:
            return "SELL", tuple(extra_hits)

    return None, tuple(extra_hits)


def crypto_momentum_hit(
    side: SignalSide,
    rsi: float,
    prev_rsi: float,
    macd_hist: float,
    macd_hist_prev: float,
    *,
    adx: Optional[float],
    plus_di: Optional[float],
    minus_di: Optional[float],
    strict_confirmed: bool,
) -> Optional[str]:
    """Momentum evidence tuned for fast crypto futures moves."""
    if strict_confirmed:
        return "rsi_macd_confirmation"
    if settings.PLANITT_RELAX_MOMENTUM:
        if side == "BUY" and macd_hist > 0:
            return "macd_direction"
        if side == "SELL" and macd_hist < 0:
            return "macd_direction"
    if settings.PLANITT_CRYPTO_FUTURES_ANALYSIS and plus_di is not None and minus_di is not None:
        spread = plus_di - minus_di
        min_spread = settings.PLANITT_CRYPTO_DI_MOMENTUM_SPREAD
        if side == "BUY" and spread >= min_spread and macd_hist > 0 and macd_hist >= macd_hist_prev:
            return "di_macd_momentum"
        if side == "SELL" and spread <= -min_spread and macd_hist < 0 and macd_hist <= macd_hist_prev:
            return "di_macd_momentum"
    return None


def detect_liquidity_sweep_setup(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float],
    *,
    side: SignalSide,
    atr: float,
) -> Optional[LiquiditySweepSetup]:
    """
    Liquidity sweep (stop hunt) + rejection — high-probability futures entry.
    Bullish: wick below swing low, close back above. Bearish: wick above swing high, close below.
    """
    if not settings.PLANITT_CRYPTO_SWEEP_SETUP_ENABLED:
        return None

    data = SMC().calculate_from_ohlc(opens, highs, lows, closes, volumes)
    lookback = settings.PLANITT_CRYPTO_SWEEP_LOOKBACK_BARS
    recent_cutoff = len(closes) - lookback
    sweeps = [s for s in data.get("sweeps", []) if s.get("index", 0) >= recent_cutoff]

    want = "bullish_sweep" if side == "BUY" else "bearish_sweep"
    for sweep in reversed(sweeps):
        if sweep.get("type") != want:
            continue
        level = float(sweep["price"])
        pad = atr * settings.ADVISOR_SMC_ZONE_ATR_PAD
        price = closes[-1]
        if side == "BUY" and price >= level - pad:
            return LiquiditySweepSetup(
                side=side,
                key_level=level,
                hits=("smc_liquidity_sweep", "smc_sweep_reclaim", "key_level_reaction_sweep"),
            )
        if side == "SELL" and price <= level + pad:
            return LiquiditySweepSetup(
                side=side,
                key_level=level,
                hits=("smc_liquidity_sweep", "smc_sweep_reject", "key_level_reaction_sweep"),
            )
    return None


def detect_vwap_setup(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float],
    *,
    side: SignalSide,
) -> Optional[VwapSetup]:
    """VWAP reclaim (long) / reject (short) — institutional intraday anchor on perps."""
    if not settings.PLANITT_CRYPTO_VWAP_SETUP_ENABLED or len(closes) < 30:
        return None

    vwap = VWAP()
    vwap.calculate_from_ohlcv(highs, lows, closes, volumes)
    val = vwap.get_current().get("vwap")
    if val is None:
        return None

    price = closes[-1]
    prev = closes[-2]
    tol = settings.PLANITT_CRYPTO_VWAP_TOLERANCE_PCT

    if side == "BUY":
        reclaimed = prev < val * (1 - tol) and price > val * (1 + tol * 0.25)
        if reclaimed:
            return VwapSetup(side=side, key_level=float(val), hits=("vwap_reclaim", "key_level_reaction_vwap"))
    else:
        rejected = prev > val * (1 + tol) and price < val * (1 - tol * 0.25)
        if rejected:
            return VwapSetup(side=side, key_level=float(val), hits=("vwap_reject", "key_level_reaction_vwap"))
    return None


def relative_volume_spike(volumes: list[float], lookback: int = 20) -> bool:
    """Crypto futures: compare to recent bar average (exchange volume is noisy)."""
    if len(volumes) < lookback + 1:
        return False
    prev = volumes[-(lookback + 1) : -1]
    avg = sum(prev) / max(len(prev), 1)
    if avg <= 0:
        return False
    return volumes[-1] / avg >= settings.PLANITT_VOLUME_MULTIPLIER
