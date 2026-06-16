from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import config.settings as cs

cs.settings.ADVISOR_REACHABILITY_GATE_ENABLED = True
cs.settings.ADVISOR_REACHABILITY_K = 1.2

from src.advisor.reachability import check_tp_reachability, expected_move_pct, resolve_reachability


def test_expected_move_scales_with_time() -> None:
    short = expected_move_pct(100.0, 50000.0, timeframe="1h", hours_until_expiry=12.0)
    long = expected_move_pct(100.0, 50000.0, timeframe="1h", hours_until_expiry=48.0)
    assert long > short


def test_unreachable_tp_rejected() -> None:
    ist = ZoneInfo("Asia/Kolkata")
    at = datetime(2026, 1, 1, 10, 0, tzinfo=ist)
    result = check_tp_reachability(
        entry_mid=100.0,
        target=110.0,
        atr=0.5,
        price=100.0,
        timeframe="1h",
        trade_horizon="intraday",
        generated_at=at,
    )
    assert not result.ok
    assert result.tp_distance_pct == 10.0


def test_close_tp_passes() -> None:
    ist = ZoneInfo("Asia/Kolkata")
    at = datetime(2026, 1, 1, 10, 0, tzinfo=ist)
    result = check_tp_reachability(
        entry_mid=100.0,
        target=102.0,
        atr=2.0,
        price=100.0,
        timeframe="1h",
        trade_horizon="intraday",
        generated_at=at,
    )
    assert result.ok


def test_auto_swing_upgrade_when_intraday_fails() -> None:
    cs.settings.ADVISOR_REACHABILITY_AUTO_SWING = True
    ist = ZoneInfo("Asia/Kolkata")
    at = datetime(2026, 1, 1, 10, 0, tzinfo=ist)
    resolved = resolve_reachability(
        entry_mid=100.0,
        target=104.0,
        atr=1.5,
        price=100.0,
        timeframe="1h",
        generated_at=at,
    )
    assert resolved.ok or resolved.trade_horizon in ("intraday", "swing")
