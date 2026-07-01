"""Swing guard tests for 4h / 1d segments."""

from __future__ import annotations

from src.advisor.swing_guards import swing_min_rr, validate_swing_signal
from src.planitt.confluence import ConfluenceFeatures


def _features(**kwargs) -> ConfluenceFeatures:
    base = dict(
        asset="XRP",
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
        confluence_hits=("swing_structure", "ema_alignment", "rsi_macd_confirmation", "volume_spike"),
        pre_confidence=0.85,
        adx=28.0,
        candlestick_pattern=None,
        candlestick_bias=None,
        candlestick_strength=0.0,
        candlestick_confirmed=False,
        agreeing_sources=5,
        mtf_score=0.9,
    )
    base.update(kwargs)
    return ConfluenceFeatures(**base)


def test_swing_min_rr_higher_than_intraday(monkeypatch):
    import src.advisor.swing_guards as sg

    monkeypatch.setattr(sg.settings, "SOP_MIN_RR", 1.3)
    monkeypatch.setattr(sg.settings, "SOP_SWING_MIN_RR", 1.8)
    assert swing_min_rr("15m") == 1.3
    assert swing_min_rr("4h") == 1.8


def test_4h_requires_structure_confluence(monkeypatch):
    import src.advisor.swing_guards as sg

    monkeypatch.setattr(sg.settings, "ADVISOR_SWING_REQUIRE_STRUCTURE", True)
    feats = _features(
        confluence_hits=("ema_alignment", "rsi_macd_confirmation", "volume_spike", "vote_macd")
    )
    ok, reason = validate_swing_signal(feats, "4h", mtf_score=0.9, tier="B")
    assert ok is False
    assert reason == "swing_no_structure_confluence"


def test_1d_requires_tier_a(monkeypatch):
    import src.advisor.swing_guards as sg

    monkeypatch.setattr(sg.settings, "ADVISOR_SWING_REQUIRE_STRUCTURE", False)
    feats = _features(timeframe="1d", pre_confidence=0.9)
    ok, reason = validate_swing_signal(feats, "1d", mtf_score=0.9, tier="B")
    assert ok is False
    assert reason and reason.startswith("swing_1d_requires_tier_a")
