from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.planitt.persistence import build_signal_document


def test_build_signal_document_open_defaults() -> None:
    now = datetime.now(timezone.utc)
    payload = {
        "asset": "BTCUSDT",
        "signal_type": "BUY",
        "entry_range": [50000.0, 50100.0],
        "take_profit": {"tp1": 51000.0, "tp2": 52000.0, "tp3": 53000.0},
        "stop_loss": 49500.0,
        "confidence": 0.83,
        "strategy": "planitt",
        "reason": "test",
        "risk_reward_ratio": "1:2.0",
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=4)).isoformat(),
    }
    doc = build_signal_document(payload=payload, symbol="BTC", timeframe="15m", dedup_key="abc")
    assert doc.status == "OPEN"
    assert doc.outcome == "open"
    assert doc.is_published is True
    assert doc.confidence_score == pytest.approx(0.83)
