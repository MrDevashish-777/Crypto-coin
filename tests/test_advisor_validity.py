"""SOP §5–6 validity and timeframe tests."""

from __future__ import annotations

from datetime import datetime

from src.advisor.validity import (
    IST,
    compute_valid_until,
    entry_miss_eligible_for_review,
    infer_swing_days,
    infer_trade_horizon,
    validate_publish_timeframe,
)


def test_intraday_valid_until_next_ist_midnight():
    start = datetime(2026, 6, 30, 17, 0, 0, tzinfo=IST)
    end = compute_valid_until("intraday", generated_at=start, timeframe="15m")
    assert end.day == 1
    assert end.month == 7
    assert end.hour == 23 and end.minute == 59


def test_swing_valid_until_capped_at_seven_days():
    start = datetime(2026, 6, 30, 10, 0, 0, tzinfo=IST)
    end = compute_valid_until("swing", generated_at=start, timeframe="1d", swing_days=7)
    assert (end.date() - start.date()).days == 7
    assert end.hour == 23


def test_scalping_timeframes_blocked():
    ok, reason = validate_publish_timeframe("5m")
    assert not ok
    assert "scalping" in (reason or "")


def test_swing_and_intraday_allowed():
    assert validate_publish_timeframe("15m")[0]
    assert validate_publish_timeframe("1h")[0]
    assert validate_publish_timeframe("4h")[0]
    assert validate_publish_timeframe("1d")[0]


def test_infer_trade_horizon():
    assert infer_trade_horizon("15m") == "intraday"
    assert infer_trade_horizon("4h") == "swing"


def test_entry_miss_within_one_percent():
    assert entry_miss_eligible_for_review(101.8, 100.0, 101.0)
    assert not entry_miss_eligible_for_review(100.0, 100.0, 101.0)
    assert not entry_miss_eligible_for_review(105.0, 100.0, 101.0)


def test_swing_days_in_range():
    assert 2 <= infer_swing_days("4h") <= 7
    assert 2 <= infer_swing_days("1d") <= 7
