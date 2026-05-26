"""Tests for advisor signal document shape and outcome fields."""

from datetime import datetime, timezone

from src.advisor.persistence import build_advisor_document
from src.advisor.schemas import AdvisorSignal


def test_advisor_document_includes_outcome_fields():
    signal = AdvisorSignal(
        pair="BTCUSDT",
        symbol="BTC",
        margin_currency="USDT",
        direction="BUY",
        trade_horizon="intraday",
        timeframe="1h",
        entry_low=100.0,
        entry_high=101.0,
        stop_loss=97.5,
        target=104.0,
        sl_pct=2.5,
        tp_pct=3.5,
        leverage=8.0,
        risk_reward="1:1.5",
        confidence=0.82,
        valid_until_ist=datetime.now(timezone.utc),
        generated_at=datetime.now(timezone.utc),
        live_price_at_signal=100.5,
        setup_type="trend_pullback",
        reason_why_token="test",
        reason_entry="test",
        reason_monitor="test",
    )
    doc = build_advisor_document(signal)
    assert doc["status"] == "OPEN"
    assert doc["outcome"] == "open"
    assert doc["source_backend"] == "coindcx_advisor"
