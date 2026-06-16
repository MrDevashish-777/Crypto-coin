"""Tests for advisor signal reconciliation replay."""

from datetime import datetime, timezone

from src.advisor.reconciliation import replay_outcome_from_candles
from src.data.models import Candle


def _candle(ts_ms: int, high: float, low: float) -> Candle:
    return Candle(
        timestamp=ts_ms,
        open=(high + low) / 2,
        high=high,
        low=low,
        close=(high + low) / 2,
        volume=1.0,
    )


def test_buy_tp_hit_on_candle():
    gen_ms = 1_000_000
    candles = [_candle(gen_ms + 60_000, high=110.0, low=99.0)]
    status, outcome, hit_price, pnl_r = replay_outcome_from_candles(
        direction="BUY",
        entry=100.0,
        tp=108.0,
        sl=95.0,
        generated_ts_ms=gen_ms,
        valid_until=None,
        candles=candles,
        latest_price=100.0,
    )
    assert status == "TP_HIT"
    assert outcome == "tp_hit"
    assert hit_price == 108.0
    assert pnl_r > 0


def test_buy_sl_before_tp_same_bar():
    gen_ms = 1_000_000
    candles = [_candle(gen_ms + 60_000, high=110.0, low=94.0)]
    status, outcome, hit_price, pnl_r = replay_outcome_from_candles(
        direction="BUY",
        entry=100.0,
        tp=108.0,
        sl=95.0,
        generated_ts_ms=gen_ms,
        valid_until=None,
        candles=candles,
        latest_price=100.0,
    )
    assert status == "SL_HIT"
    assert outcome == "sl_hit"
    assert hit_price == 95.0
    assert pnl_r == -1.0


def test_expired_when_past_valid_until():
    gen_ms = 1_000_000
    valid_until = datetime(2025, 1, 2, tzinfo=timezone.utc)
    now = datetime(2025, 1, 3, tzinfo=timezone.utc)
    status, outcome, _, pnl_r = replay_outcome_from_candles(
        direction="BUY",
        entry=100.0,
        tp=108.0,
        sl=95.0,
        generated_ts_ms=gen_ms,
        valid_until=valid_until,
        candles=[],
        latest_price=100.0,
        now=now,
    )
    assert status == "EXPIRED"
    assert outcome == "expired"
    assert pnl_r == 0.0


def test_live_price_tp_when_no_candle_hit():
    gen_ms = 1_000_000
    status, outcome, _, pnl_r = replay_outcome_from_candles(
        direction="SELL",
        entry=100.0,
        tp=92.0,
        sl=105.0,
        generated_ts_ms=gen_ms,
        valid_until=None,
        candles=[],
        latest_price=91.0,
    )
    assert status == "TP_HIT"
    assert outcome == "tp_hit"
    assert pnl_r > 0
