"""SOP gate validation tests."""

from __future__ import annotations

from src.advisor.sop_gates import validate_levels


def test_validate_levels_buy_ok() -> None:
    result = validate_levels(
        direction="BUY",
        entry_low=100.0,
        entry_high=101.0,
        stop_loss=97.5,
        target=106.0,
        live_price=100.5,
        sl_pct=2.5,
        tp_pct=5.5,
        leverage=8.0,
        risk_reward="1:2.0",
        confidence=0.75,
    )
    assert result.ok


def test_validate_levels_rejects_low_confidence() -> None:
    result = validate_levels(
        direction="BUY",
        entry_low=100.0,
        entry_high=101.0,
        stop_loss=97.5,
        target=104.0,
        live_price=100.5,
        sl_pct=2.5,
        tp_pct=3.5,
        leverage=8.0,
        risk_reward="1:1.6",
        confidence=0.50,
    )
    assert not result.ok
    assert result.reason


def test_validate_levels_rejects_wide_entry() -> None:
    result = validate_levels(
        direction="BUY",
        entry_low=100.0,
        entry_high=105.0,
        stop_loss=97.0,
        target=110.0,
        live_price=102.0,
        sl_pct=2.5,
        tp_pct=5.0,
        leverage=8.0,
        risk_reward="1:2",
        confidence=0.8,
    )
    assert not result.ok
