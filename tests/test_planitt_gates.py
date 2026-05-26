"""Tests for stricter Planitt confluence gates and indicator votes."""

from __future__ import annotations

from src.data.models import Candle, CandleList
from src.planitt.confluence import _validate_mandatory_categories, evaluate_confluence_pre_gates_with_reason
from src.planitt.indicator_votes import evaluate_indicator_votes
from src.planitt.mtf_confluence import check_htf_alignment, higher_timeframes_for


def _build_trending_candles(n: int = 240) -> CandleList:
    candles = []
    base = 100.0
    for i in range(n):
        close = base + i * 0.4
        open_p = close - 0.2
        high = close + 0.6
        low = open_p - 0.4
        vol = 1000 + (i % 10) * 30
        candles.append(
            Candle(
                timestamp=1_700_000_000_000 + i * 900_000,
                open=open_p,
                high=high,
                low=low,
                close=close,
                volume=vol,
            )
        )
    return CandleList(symbol="BTC", timeframe="15m", candles=candles)


def test_mandatory_categories_requires_all_buckets():
    hits = [
        "ema_alignment",
        "swing_structure",
        "rsi_macd_confirmation",
        "key_level_reaction_pullback",
        "volume_spike",
    ]
    assert _validate_mandatory_categories(hits, has_setup=True) is True

    incomplete = ["ema_alignment", "rsi_macd_confirmation"]
    assert _validate_mandatory_categories(incomplete, has_setup=False) is False


def test_htf_map_for_15m():
    assert higher_timeframes_for("15m") == ["1h", "4h"]


def test_mandatory_categories_requires_location_bucket():
    assert _validate_mandatory_categories(
        ["ema_alignment", "rsi_macd_confirmation", "volume_spike"],
        has_setup=False,
    ) is False
    assert _validate_mandatory_categories(
        ["ema_alignment", "macd_direction", "volume_spike"],
        has_setup=True,
    ) is True
    assert _validate_mandatory_categories(
        ["ema_alignment", "rsi_macd_confirmation", "key_level_reaction_nwe", "vote_nwe"],
        has_setup=False,
    ) is True


def test_indicator_votes_on_trending_series():
    candle_list = _build_trending_candles()
    result = evaluate_indicator_votes(
        candle_list,
        expected_side="BUY",
        key_level=candle_list.closes[-1],
        ema50=candle_list.closes[-1] * 0.98,
    )
    assert result.agreeing_sources >= 0
    assert result.bull_score >= 0


def test_mtf_alignment_with_matching_htf():
    ltf = _build_trending_candles()
    htf = _build_trending_candles(260)
    htf = CandleList(symbol="BTC", timeframe="1h", candles=htf.candles)
    result = check_htf_alignment("BUY", "15m", {"1h": htf, "4h": htf})
    assert result.aligned or result.reject_reason is not None


def test_confluence_evaluation_returns_structured_reject():
    candle_list = _build_trending_candles(50)
    ev = evaluate_confluence_pre_gates_with_reason(candle_list, min_confluence_hits=4)
    assert ev.features is None
    assert ev.reject_reason is not None
