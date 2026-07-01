"""Segment-specific publish gates — tune SELL / swing / Tier A instead of blocking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from config.settings import settings
from src.advisor.reachability import ReachabilityResult
from src.advisor.validity import infer_trade_horizon
from src.analysis.backtest_config import passes_quality_tier
from src.planitt.confluence import ConfluenceFeatures
from src.signals.market_regime import MarketRegime

Direction = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class PublishThresholds:
    min_confidence: float
    min_composite: float
    min_mtf: float
    min_confluence_hits: int
    min_quality_tier: str
    min_agreeing_sources: int
    min_vote_margin: float
    strict_htf: bool
    require_swing_reachability: bool


def _is_swing_timeframe(timeframe: str) -> bool:
    return timeframe in ("4h", "1d") or infer_trade_horizon(timeframe) == "swing"


def _is_15m(timeframe: str) -> bool:
    return timeframe == "15m"


def _is_1h_intraday(timeframe: str) -> bool:
    return timeframe == "1h"


def _is_4h(timeframe: str) -> bool:
    return timeframe == "4h"


def _is_1d(timeframe: str) -> bool:
    return timeframe == "1d"


def _swing_profile(
    base: PublishThresholds,
    *,
    min_confidence: float,
    min_composite: float,
    min_mtf: float,
    min_confluence_hits: int,
    min_agreeing_sources: int,
    min_vote_margin: float,
    min_quality_tier: str,
) -> PublishThresholds:
    return PublishThresholds(
        min_confidence=min_confidence,
        min_composite=min_composite,
        min_mtf=min_mtf,
        min_confluence_hits=min_confluence_hits,
        min_quality_tier=min_quality_tier,
        min_agreeing_sources=min_agreeing_sources,
        min_vote_margin=min_vote_margin,
        strict_htf=True,
        require_swing_reachability=True,
    )


def _intraday_profile(
    base: PublishThresholds,
    *,
    min_confidence: float,
    min_composite: float,
    min_mtf: float,
    min_confluence_hits: int,
    min_agreeing_sources: int,
    min_vote_margin: float,
    min_quality_tier: str,
) -> PublishThresholds:
    return PublishThresholds(
        min_confidence=min_confidence,
        min_composite=min_composite,
        min_mtf=min_mtf,
        min_confluence_hits=min_confluence_hits,
        min_quality_tier=min_quality_tier,
        min_agreeing_sources=min_agreeing_sources,
        min_vote_margin=min_vote_margin,
        strict_htf=False,
        require_swing_reachability=False,
    )


def get_publish_thresholds(direction: Direction, timeframe: str) -> PublishThresholds:
    """
    SOP baseline (1h BUY intraday) with stricter overlays for historically weak segments.

    Weak live segments were caused by:
    - SELL: shorts against HTF bull trend + soft MTF alignment
    - 4h/1d/swing: TP beyond SOP validity window
    - Tier A: high score without extra confirmation on those segments
    """
    base = PublishThresholds(
        min_confidence=settings.ADVISOR_MIN_CONFIDENCE,
        min_composite=settings.ADVISOR_MIN_COMPOSITE_SCORE,
        min_mtf=settings.ADVISOR_MIN_MTF_SCORE,
        min_confluence_hits=settings.ADVISOR_MIN_CONFLUENCE_HITS,
        min_quality_tier=settings.ADVISOR_PUBLISH_MIN_QUALITY_TIER,
        min_agreeing_sources=settings.ADVISOR_MIN_AGREEING_SOURCES,
        min_vote_margin=settings.ADVISOR_MIN_VOTE_MARGIN,
        strict_htf=False,
        require_swing_reachability=False,
    )

    if _is_15m(timeframe):
        tier = (
            settings.ADVISOR_BUY_PUBLISH_MIN_QUALITY_TIER
            if direction == "BUY"
            else settings.ADVISOR_SELL_PUBLISH_MIN_QUALITY_TIER
        )
        return _intraday_profile(
            base,
            min_confidence=settings.ADVISOR_15M_MIN_CONFIDENCE,
            min_composite=settings.ADVISOR_15M_MIN_COMPOSITE_SCORE,
            min_mtf=settings.ADVISOR_15M_MIN_MTF_SCORE,
            min_confluence_hits=settings.ADVISOR_15M_MIN_CONFLUENCE_HITS,
            min_agreeing_sources=settings.ADVISOR_15M_MIN_AGREEING_SOURCES,
            min_vote_margin=settings.ADVISOR_15M_MIN_VOTE_MARGIN,
            min_quality_tier=tier,
        )

    if _is_1h_intraday(timeframe):
        tier = (
            settings.ADVISOR_BUY_PUBLISH_MIN_QUALITY_TIER
            if direction == "BUY"
            else settings.ADVISOR_SELL_PUBLISH_MIN_QUALITY_TIER
        )
        return _intraday_profile(
            base,
            min_confidence=settings.ADVISOR_1H_MIN_CONFIDENCE,
            min_composite=settings.ADVISOR_1H_MIN_COMPOSITE_SCORE,
            min_mtf=settings.ADVISOR_1H_MIN_MTF_SCORE,
            min_confluence_hits=settings.ADVISOR_1H_MIN_CONFLUENCE_HITS,
            min_agreeing_sources=settings.ADVISOR_1H_MIN_AGREEING_SOURCES,
            min_vote_margin=settings.ADVISOR_1H_MIN_VOTE_MARGIN,
            min_quality_tier=tier,
        )

    if _is_4h(timeframe):
        tier = settings.ADVISOR_4H_PUBLISH_MIN_QUALITY_TIER
        return _swing_profile(
            base,
            min_confidence=settings.ADVISOR_4H_MIN_CONFIDENCE,
            min_composite=settings.ADVISOR_4H_MIN_COMPOSITE_SCORE,
            min_mtf=settings.ADVISOR_4H_MIN_MTF_SCORE,
            min_confluence_hits=settings.ADVISOR_4H_MIN_CONFLUENCE_HITS,
            min_agreeing_sources=settings.ADVISOR_4H_MIN_AGREEING_SOURCES,
            min_vote_margin=settings.ADVISOR_4H_MIN_VOTE_MARGIN,
            min_quality_tier=tier,
        )

    if _is_1d(timeframe):
        tier = settings.ADVISOR_1D_PUBLISH_MIN_QUALITY_TIER
        return _swing_profile(
            base,
            min_confidence=settings.ADVISOR_1D_MIN_CONFIDENCE,
            min_composite=settings.ADVISOR_1D_MIN_COMPOSITE_SCORE,
            min_mtf=settings.ADVISOR_1D_MIN_MTF_SCORE,
            min_confluence_hits=settings.ADVISOR_1D_MIN_CONFLUENCE_HITS,
            min_agreeing_sources=settings.ADVISOR_1D_MIN_AGREEING_SOURCES,
            min_vote_margin=settings.ADVISOR_1D_MIN_VOTE_MARGIN,
            min_quality_tier=tier,
        )

    if direction == "BUY" and not _is_swing_timeframe(timeframe):
        return PublishThresholds(
            min_confidence=min(base.min_confidence, settings.ADVISOR_BUY_MIN_CONFIDENCE),
            min_composite=min(base.min_composite, settings.ADVISOR_BUY_MIN_COMPOSITE_SCORE),
            min_mtf=min(base.min_mtf, settings.ADVISOR_BUY_MIN_MTF_SCORE),
            min_confluence_hits=min(base.min_confluence_hits, settings.ADVISOR_BUY_MIN_CONFLUENCE_HITS),
            min_quality_tier=settings.ADVISOR_BUY_PUBLISH_MIN_QUALITY_TIER,
            min_agreeing_sources=min(base.min_agreeing_sources, settings.ADVISOR_BUY_MIN_AGREEING_SOURCES),
            min_vote_margin=min(base.min_vote_margin, settings.ADVISOR_BUY_MIN_VOTE_MARGIN),
            strict_htf=False,
            require_swing_reachability=False,
        )

    if direction == "SELL" and not _is_swing_timeframe(timeframe):
        return PublishThresholds(
            min_confidence=max(base.min_confidence, settings.ADVISOR_SELL_MIN_CONFIDENCE),
            min_composite=max(base.min_composite, settings.ADVISOR_SELL_MIN_COMPOSITE_SCORE),
            min_mtf=max(base.min_mtf, settings.ADVISOR_SELL_MIN_MTF_SCORE),
            min_confluence_hits=max(base.min_confluence_hits, settings.ADVISOR_SELL_MIN_CONFLUENCE_HITS),
            min_quality_tier=settings.ADVISOR_SELL_PUBLISH_MIN_QUALITY_TIER,
            min_agreeing_sources=max(base.min_agreeing_sources, settings.ADVISOR_SELL_MIN_AGREEING_SOURCES),
            min_vote_margin=max(base.min_vote_margin, settings.ADVISOR_SELL_MIN_VOTE_MARGIN),
            strict_htf=False,
            require_swing_reachability=False,
        )

    return base


def validate_sell_regime(
    side: Direction,
    *,
    adx: float | None,
    regime: MarketRegime | None,
    timeframe: str = "1h",
) -> tuple[bool, str | None]:
    """SELL only when bearish structure is confirmed — avoids shorting bull trends."""
    if side != "SELL":
        return True, None

    if _is_swing_timeframe(timeframe) and regime == MarketRegime.RANGING:
        return False, "swing_sell_ranging_blocked"

    min_adx = settings.ADVISOR_SELL_MIN_ADX
    if _is_15m(timeframe):
        min_adx = settings.ADVISOR_15M_SELL_MIN_ADX
    elif _is_1h_intraday(timeframe):
        min_adx = settings.ADVISOR_1H_SELL_MIN_ADX
    elif timeframe == "4h":
        min_adx = settings.ADVISOR_4H_SELL_MIN_ADX
    elif timeframe == "1d":
        min_adx = settings.ADVISOR_1D_SELL_MIN_ADX

    if adx is None or adx < min_adx:
        return False, f"sell_adx_below_{adx or 0:.1f}"

    if regime == MarketRegime.TRENDING_UP:
        return False, "sell_against_trending_up"

    if regime == MarketRegime.RANGING and not settings.ADVISOR_SELL_ALLOW_RANGING:
        return False, "sell_ranging_blocked"

    return True, None


def vote_thresholds_for_side(direction: Direction, timeframe: str) -> tuple[int, float]:
    profile = get_publish_thresholds(direction, timeframe)
    return profile.min_agreeing_sources, profile.min_vote_margin


def validate_tier_a(
    *,
    tier: str,
    direction: Direction,
    timeframe: str,
    features: ConfluenceFeatures,
    mtf_score: float,
    reach: ReachabilityResult,
    risk_reward_value: float,
) -> tuple[bool, str | None]:
    """Tier A needs SOP high-confidence confirmation — swing only; intraday uses segment gates."""
    if tier != "A":
        return True, None

    if not _is_swing_timeframe(timeframe):
        return True, None

    if features.pre_confidence < settings.SOP_HIGH_CONF_THRESHOLD:
        return False, f"tier_a_conf_below_{settings.SOP_HIGH_CONF_THRESHOLD}"

    if features.agreeing_sources < settings.SOP_HIGH_CONF_MIN_SOURCES:
        return False, f"tier_a_sources_{features.agreeing_sources}"

    if risk_reward_value < settings.SOP_HIGH_CONF_MIN_RR:
        return False, f"tier_a_rr_below_{settings.SOP_HIGH_CONF_MIN_RR}"

    if direction == "SELL":
        if mtf_score < settings.ADVISOR_TIER_A_SELL_MIN_MTF:
            return False, f"tier_a_sell_mtf_{mtf_score:.2f}"
        if features.adx is not None and features.adx < settings.ADVISOR_SELL_MIN_ADX:
            return False, "tier_a_sell_adx"

    if _is_swing_timeframe(timeframe):
        if reach.trade_horizon != "swing" or not reach.ok:
            return False, "tier_a_swing_reachability"
        if mtf_score < settings.ADVISOR_SWING_MIN_MTF_SCORE:
            return False, f"tier_a_swing_mtf_{mtf_score:.2f}"

    return True, None


def passes_high_accuracy_mode(
    features: ConfluenceFeatures,
    *,
    composite_score: float,
) -> tuple[bool, str | None]:
    """Extra publish floor when ADVISOR_HIGH_ACCURACY_MODE is enabled."""
    if not settings.ADVISOR_HIGH_ACCURACY_MODE:
        return True, None
    if len(features.confluence_hits) < settings.ADVISOR_HIGH_ACCURACY_MIN_CONFLUENCE_HITS:
        return False, f"high_accuracy_hits_{len(features.confluence_hits)}"
    if features.agreeing_sources < settings.ADVISOR_HIGH_ACCURACY_MIN_AGREEING_SOURCES:
        return False, f"high_accuracy_sources_{features.agreeing_sources}"
    if composite_score < settings.ADVISOR_QUALITY_TIER_A_MIN:
        return False, f"high_accuracy_composite_{composite_score:.2f}"
    return True, None


def passes_segment_quality(
    *,
    features: ConfluenceFeatures,
    composite_score: float,
    tier: str,
    timeframe: str,
) -> tuple[bool, str | None]:
    profile = get_publish_thresholds(features.side, timeframe)

    if composite_score < profile.min_composite:
        return False, f"composite_below_{composite_score:.2f}"
    if features.mtf_score < profile.min_mtf:
        return False, f"mtf_below_{features.mtf_score:.2f}"
    if not passes_quality_tier(tier, profile.min_quality_tier):
        return False, f"quality_tier_{tier}"
    if features.pre_confidence < profile.min_confidence:
        return False, f"confidence_{features.pre_confidence:.2f}"
    if len(features.confluence_hits) < profile.min_confluence_hits:
        return False, f"confluence_hits_{len(features.confluence_hits)}"

    return True, None


def mtf_min_agreeing_for(direction: Direction, timeframe: str) -> int:
    """SOP requires 2 HTF for swing; SELL requires all available HTFs."""
    htfs_count = {"15m": 2, "1h": 2, "4h": 1, "1d": 0}.get(timeframe, 1)
    if htfs_count == 0:
        return 0
    if direction == "BUY" and not _is_swing_timeframe(timeframe):
        return 1
    if direction == "SELL" and not _is_swing_timeframe(timeframe):
        return 1
    if direction == "SELL" or _is_swing_timeframe(timeframe):
        return htfs_count
    return min(htfs_count, max(1, settings.PLANITT_MTF_MIN_AGREEING))
