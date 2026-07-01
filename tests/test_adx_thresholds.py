"""ADX threshold per timeframe."""

from __future__ import annotations

from src.planitt.confluence import adx_trend_threshold_for_timeframe


def test_15m_adx_lower_than_swing(monkeypatch):
    import config.settings as sm

    monkeypatch.setattr(sm.settings, "PLANITT_15M_ADX_THRESHOLD", 14.0)
    monkeypatch.setattr(sm.settings, "PLANITT_4H_ADX_THRESHOLD", 20.0)
    assert adx_trend_threshold_for_timeframe("15m") == 14.0
    assert adx_trend_threshold_for_timeframe("4h") == 20.0
