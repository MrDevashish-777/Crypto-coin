"""Weekly allocation tracker tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.advisor.allocation import WeeklyAllocationTracker


def test_weekly_cap_blocks_publish() -> None:
    tracker = WeeklyAllocationTracker()
    now = datetime.now(timezone.utc)
    for i in range(14):
        tracker.record(f"SYM{i}", at=now - timedelta(hours=i))
    ok, reason = tracker.can_publish("BTC", now=now)
    assert not ok
    assert reason == "weekly_cap_reached"


def test_duplicate_symbol_same_day() -> None:
    tracker = WeeklyAllocationTracker()
    now = datetime.now(timezone.utc)
    tracker.record("BTC", at=now)
    ok, reason = tracker.can_publish("BTC", now=now)
    assert not ok
    assert reason == "duplicate_symbol_today"
