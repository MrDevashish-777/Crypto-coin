"""Adaptive bot tuning tests."""

from __future__ import annotations

from src.advisor.adaptive import (
    adaptive_composite_adjustment,
    bucket_level_adjustments,
    regime_level_tuning,
)
from src.advisor.macro_trend import macro_alignment_score


def test_macro_alignment_buy_bullish():
    assert macro_alignment_score("BUY", {}, 0) == 0.0


def test_adaptive_composite_boosts_aligned_buy(monkeypatch):
    import src.advisor.adaptive as ad

    monkeypatch.setattr(ad.settings, "ADVISOR_ADAPTIVE_MACRO_SCORING", True)
    monkeypatch.setattr(ad.settings, "ADVISOR_MACRO_ALIGNMENT_WEIGHT", 0.10)
    monkeypatch.setattr(ad.settings, "ADVISOR_ADAPTIVE_BUCKET_RANKING", False)
    base = 0.85
    aligned = adaptive_composite_adjustment(base, side="BUY", macro_alignment=1.0)
    counter = adaptive_composite_adjustment(base, side="BUY", macro_alignment=-1.0)
    assert aligned > base
    assert counter < base


def test_ranging_wider_sl_than_trending(monkeypatch):
    import src.advisor.adaptive as ad

    monkeypatch.setattr(ad.settings, "ADVISOR_RANGING_SL_SCALE", 1.15)
    monkeypatch.setattr(ad.settings, "ADVISOR_RANGING_TP_SCALE", 0.92)
    r_sl, r_tp = regime_level_tuning("ranging")
    t_sl, t_tp = regime_level_tuning("trending")
    assert r_sl > t_sl
    assert r_tp < t_tp


def test_negative_bucket_widens_sl(monkeypatch, tmp_path):
    import json
    import src.advisor.adaptive as ad
    from src.advisor import live_performance as lp

    path = tmp_path / "live_bucket_expectancy.json"
    path.write_text(
        json.dumps(
            {
                "SEI_15m_BUY": {
                    "wins": 1,
                    "losses": 4,
                    "net_r": -3.0,
                    "expectancy": -0.6,
                    "trades": 5,
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(lp, "LIVE_BUCKET_PATH", path)
    lp.load_live_bucket_expectancy.cache_clear()
    monkeypatch.setattr(ad.settings, "ADVISOR_ADAPTIVE_BUCKET_LEVELS", True)
    monkeypatch.setattr(ad.settings, "ADVISOR_ADAPTIVE_BUCKET_MIN_TRADES", 3)
    sl, tp = bucket_level_adjustments("SEI", "15m", "BUY")
    assert sl > 1.0
    assert tp < 1.0
