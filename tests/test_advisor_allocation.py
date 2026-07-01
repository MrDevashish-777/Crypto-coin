"""Weekly allocation tracker tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.advisor.allocation import (
    WeeklyAllocationTracker,
    filter_publish_queue,
    is_scannable_symbol,
    majors_rank_boost,
    weekly_allocation_stats,
)


def test_weekly_cap_blocks_publish(monkeypatch) -> None:
    monkeypatch.setattr("src.advisor.allocation.settings.MAX_WEEKLY_SIGNALS", 14)
    monkeypatch.setattr("src.advisor.allocation.settings.MAX_DAILY_SIGNALS", 50)
    tracker = WeeklyAllocationTracker()
    now = datetime.now(timezone.utc)
    for i in range(14):
        tracker.record(f"SYM{i}", at=now - timedelta(hours=i))
    ok, reason = tracker.can_publish("BTC", now=now)
    assert not ok
    assert reason == "weekly_cap_reached"


def test_duplicate_symbol_cooldown() -> None:
    tracker = WeeklyAllocationTracker()
    now = datetime.now(timezone.utc)
    tracker.record("BTC", at=now)
    ok, reason = tracker.can_publish("BTC", now=now, timeframe="15m")
    assert not ok
    assert reason and reason.startswith("duplicate_symbol_cooldown")


def test_low_cap_symbol_blocked(monkeypatch) -> None:
    monkeypatch.setattr("src.advisor.allocation.settings.ADVISOR_BLOCK_LOW_CAP_SYMBOLS", True)
    ok, reason = is_scannable_symbol("RUNE")
    assert not ok
    assert reason == "low_cap_blocked_RUNE"


def test_btc_deficit_blocks_alt(monkeypatch) -> None:
    monkeypatch.setattr("src.advisor.allocation.settings.ADVISOR_STRICT_ALLOCATION", True)
    monkeypatch.setattr("src.advisor.allocation.settings.MIN_WEEKLY_BTC_PCT", 0.20)
    monkeypatch.setattr("src.advisor.allocation.settings.MIN_WEEKLY_MAJORS_PCT", 0.35)
    monkeypatch.setattr("src.advisor.allocation.settings.MAX_WEEKLY_MAJORS_PCT", 0.40)
    tracker = WeeklyAllocationTracker()
    now = datetime.now(timezone.utc)
    for sym in ("XRP", "AVAX", "ARB"):
        tracker.record(sym, at=now - timedelta(hours=1))
    ok, reason = tracker.can_publish("OP", now=now, timeframe="15m")
    assert not ok
    assert reason in ("btc_allocation_deficit", "majors_allocation_deficit")


def test_majors_cap_blocks_extra_major(monkeypatch) -> None:
    monkeypatch.setattr("src.advisor.allocation.settings.ADVISOR_STRICT_ALLOCATION", True)
    monkeypatch.setattr("src.advisor.allocation.settings.MIN_WEEKLY_BTC_PCT", 0.20)
    monkeypatch.setattr("src.advisor.allocation.settings.MIN_WEEKLY_MAJORS_PCT", 0.35)
    monkeypatch.setattr("src.advisor.allocation.settings.MAX_WEEKLY_MAJORS_PCT", 0.40)
    monkeypatch.setattr("src.advisor.allocation.settings.ADVISOR_SYMBOL_COOLDOWN_HOURS_15M", 0)
    tracker = WeeklyAllocationTracker()
    now = datetime.now(timezone.utc)
    for i, sym in enumerate(("BTC", "ETH", "SOL", "BTC", "ETH")):
        tracker.record(sym, at=now - timedelta(hours=i + 2))
    ok, reason = tracker.can_publish("SOL", now=now, timeframe="15m")
    assert not ok
    assert reason == "majors_allocation_cap"


def test_majors_rank_boost_when_deficit(monkeypatch) -> None:
    monkeypatch.setattr("src.advisor.allocation.settings.MIN_WEEKLY_MAJORS_PCT", 0.35)
    stats = weekly_allocation_stats(
        [{"symbol": "XRP", "at": datetime.now(timezone.utc).isoformat()} for _ in range(5)]
    )
    assert majors_rank_boost("BTC", stats) > majors_rank_boost("XRP", stats)


def test_filter_publish_queue_majors_only_when_btc_deficit(monkeypatch) -> None:
    monkeypatch.setattr("src.advisor.allocation.settings.ADVISOR_STRICT_ALLOCATION", True)
    monkeypatch.setattr("src.advisor.allocation.settings.MIN_WEEKLY_BTC_PCT", 0.20)
    stats = weekly_allocation_stats(
        [{"symbol": "XRP", "at": datetime.now(timezone.utc).isoformat()} for _ in range(5)]
    )
    queue = [(1.0, "NEAR", "15m", {}), (0.9, "BTC", "15m", {})]
    filtered, mode = filter_publish_queue(queue, stats)
    assert mode == "majors_only_allocation_deficit"
    assert filtered == [(0.9, "BTC", "15m", {})]
