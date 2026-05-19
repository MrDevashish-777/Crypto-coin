from __future__ import annotations

from datetime import datetime, timezone

from src.signals.signal import format_planitt_payload


def test_planitt_payload_contract_fields() -> None:
    payload = format_planitt_payload(
        asset="BTCUSDT",
        signal_type="BUY",
        entry_range=[50000.0, 50100.0],
        stop_loss=49500.0,
        take_profit={"tp1": 51000.0, "tp2": 52000.0, "tp3": 53000.0},
        risk_reward_ratio="1:2.0",
        confidence=82,
        timeframe="15m",
        strategy="planitt",
        reason="test",
        validity="2-4 hours",
        created_at=datetime.now(timezone.utc),
    )
    assert payload["signal_type"] == "BUY"
    assert payload["take_profit"]["tp3"] > payload["take_profit"]["tp2"]
