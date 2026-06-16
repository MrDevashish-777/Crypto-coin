"""Tests for live performance gates and direction/universe filters."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.advisor.live_performance import passes_live_bucket


def test_passes_live_bucket_allows_unknown_bucket(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert passes_live_bucket("BTC", "1h", direction="BUY")[0] is True


def test_passes_live_bucket_rejects_negative(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "config"
    cfg.mkdir()
    path = cfg / "live_bucket_expectancy.json"
    path.write_text(
        json.dumps(
            {
                "ETH_4h_SELL": {
                    "wins": 0,
                    "losses": 5,
                    "net_r": -5.0,
                    "expectancy": -1.0,
                    "win_rate_pct": 0.0,
                    "trades": 5,
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("src.advisor.live_performance.LIVE_BUCKET_PATH", path)
    from src.advisor import live_performance

    live_performance.load_live_bucket_expectancy.cache_clear()

    ok, reason = passes_live_bucket("ETH", "4h", direction="SELL", min_trades=2)
    assert ok is False
    assert reason and "live_bucket" in reason


def test_advisor_allowed_directions_buy_only(monkeypatch):
    monkeypatch.setenv("ADVISOR_ALLOWED_DIRECTIONS", "BUY")
    from config.settings import Settings

    s = Settings(_env_file=None)
    assert s.advisor_allowed_directions == frozenset({"BUY"})


def test_blocked_timeframes_removed_from_scan(monkeypatch):
    monkeypatch.setenv("ADVISOR_SCAN_TIMEFRAMES", "15m,1h,4h,1d")
    monkeypatch.setenv("ADVISOR_BLOCKED_TIMEFRAMES", "4h,1d")
    from config.settings import Settings

    s = Settings(_env_file=None)
    assert s.advisor_scan_timeframes == ["15m", "1h"]
