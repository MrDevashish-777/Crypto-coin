"""Tests for advisor narrative generation (LLM optional, template fallback)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.advisor.narrative import default_narrative, generate_narrative
from src.planitt.confluence import ConfluenceFeatures


def _sample_features() -> ConfluenceFeatures:
    return ConfluenceFeatures(
        asset="BTC",
        timeframe="1h",
        side="BUY",
        setup_type="trend_pullback",
        price=67000.0,
        atr=800.0,
        ema20=66500.0,
        ema50=65000.0,
        ema200=62000.0,
        rsi=58.0,
        macd_hist=120.0,
        macd_hist_prev=90.0,
        volume=1_000_000.0,
        volume_ratio=1.35,
        key_level=66000.0,
        breakout_level=None,
        confluence_hits=("ema_stack", "rsi_momentum", "volume_surge"),
        pre_confidence=0.78,
        adx=28.5,
        candlestick_pattern=None,
        candlestick_bias=None,
        candlestick_strength=0.0,
        candlestick_confirmed=False,
        agreeing_sources=6,
        mtf_score=1.0,
    )


def _sample_levels() -> dict:
    return {
        "entry_low": 66800.0,
        "entry_high": 67200.0,
        "stop_loss": 65500.0,
        "target": 69000.0,
        "leverage": 8.0,
        "risk_reward": "1:2.0",
    }


@pytest.mark.asyncio
async def test_generate_narrative_uses_llm_when_available():
    features = _sample_features()
    levels = _sample_levels()
    mock_agent = MagicMock()
    mock_agent.generate_advisor_narrative = AsyncMock(
        return_value=("Why BTC", "Entry on pullback", "Monitor SL and TP"),
    )
    why, entry, monitor = await generate_narrative(
        features, pair="BTC/USDT", levels=levels, llm_agent=mock_agent,
    )
    assert why == "Why BTC"
    assert entry == "Entry on pullback"
    assert monitor == "Monitor SL and TP"
    mock_agent.generate_advisor_narrative.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_narrative_falls_back_when_llm_returns_none():
    features = _sample_features()
    levels = _sample_levels()
    mock_agent = MagicMock()
    mock_agent.generate_advisor_narrative = AsyncMock(return_value=None)
    why, entry, monitor = await generate_narrative(
        features, pair="BTC/USDT", levels=levels, llm_agent=mock_agent,
    )
    expected = default_narrative(features, pair="BTC/USDT", levels=levels)
    assert (why, entry, monitor) == expected


@pytest.mark.asyncio
async def test_generate_narrative_falls_back_when_llm_raises():
    features = _sample_features()
    levels = _sample_levels()
    mock_agent = MagicMock()
    mock_agent.generate_advisor_narrative = AsyncMock(side_effect=ConnectionError("ollama down"))
    why, entry, monitor = await generate_narrative(
        features, pair="BTC/USDT", levels=levels, llm_agent=mock_agent,
    )
    assert "BTC/USDT" in why
    assert "65500" in monitor or "69000" in monitor
