"""Tests for live bucket win-rate gating."""

from __future__ import annotations

import json

from src.advisor import live_performance as lp


def test_passes_live_bucket_blocks_low_win_rate(monkeypatch, tmp_path):
    path = tmp_path / "live_bucket_expectancy.json"
    path.write_text(
        json.dumps(
            {
                "NEAR_15m_BUY": {
                    "wins": 2,
                    "losses": 8,
                    "net_r": -6.0,
                    "expectancy": -0.6,
                    "win_rate_pct": 20.0,
                    "trades": 10,
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(lp, "LIVE_BUCKET_PATH", path)
    lp.load_live_bucket_expectancy.cache_clear()

    ok, reason = lp.passes_live_bucket(
        "NEAR",
        "15m",
        direction="BUY",
        min_trades=3,
        min_expectancy=-1.0,
        min_win_rate=0.55,
    )
    assert ok is False
    assert reason and "live_bucket_wr" in reason


def test_passes_live_bucket_allows_unknown_bucket(monkeypatch, tmp_path):
    path = tmp_path / "live_bucket_expectancy.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(lp, "LIVE_BUCKET_PATH", path)
    lp.load_live_bucket_expectancy.cache_clear()

    ok, reason = lp.passes_live_bucket("SOL", "15m", direction="BUY", min_win_rate=0.70)
    assert ok is True
    assert reason is None
