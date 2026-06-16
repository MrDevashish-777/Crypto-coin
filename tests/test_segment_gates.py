"""Tests for SOP segment gates (SELL / swing / Tier A tuning)."""

from __future__ import annotations

from src.advisor.reachability import ReachabilityResult
from src.advisor.segment_gates import (
    get_publish_thresholds,
    validate_sell_regime,
    validate_tier_a,
)
from src.planitt.confluence import ConfluenceFeatures
from src.signals.market_regime import MarketRegime


def _features(**kwargs) -> ConfluenceFeatures:
    base = dict(
        asset="BTC",
        timeframe="4h",
        side="SELL",
        setup_type="trend_pullback",
        price=100.0,
        atr=1.0,
        ema20=99.0,
        ema50=98.0,
        ema200=97.0,
        rsi=45.0,
        macd_hist=-0.1,
        macd_hist_prev=-0.2,
        volume=1000.0,
        volume_ratio=1.2,
        key_level=100.0,
        breakout_level=None,
        confluence_hits=("vote_macd", "vote_rsi"),
        pre_confidence=0.88,
        adx=26.0,
        candlestick_pattern=None,
        candlestick_bias=None,
        candlestick_strength=0.0,
        candlestick_confirmed=False,
        agreeing_sources=6,
        mtf_score=0.96,
    )
    base.update(kwargs)
    return ConfluenceFeatures(**base)


def test_sell_stricter_than_buy_thresholds():
    buy = get_publish_thresholds("BUY", "1h")
    sell = get_publish_thresholds("SELL", "4h")
    assert sell.min_confidence > buy.min_confidence
    assert sell.strict_htf is True
    assert sell.require_swing_reachability is True


def test_sell_rejects_trending_up():
    ok, reason = validate_sell_regime("SELL", adx=28.0, regime=MarketRegime.TRENDING_UP)
    assert ok is False
    assert reason == "sell_against_trending_up"


def test_sell_allows_trending_down():
    ok, _ = validate_sell_regime("SELL", adx=28.0, regime=MarketRegime.TRENDING_DOWN)
    assert ok is True


def test_tier_a_sell_requires_high_mtf():
    reach = ReachabilityResult(True, None, 2.0, 3.0, "swing", 72.0)
    features = _features(side="SELL", mtf_score=0.80, agreeing_sources=6)
    ok, reason = validate_tier_a(
        tier="A",
        direction="SELL",
        timeframe="4h",
        features=features,
        mtf_score=0.80,
        reach=reach,
        risk_reward_value=1.8,
    )
    assert ok is False
    assert reason and "tier_a_sell_mtf" in reason
