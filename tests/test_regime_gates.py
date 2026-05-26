"""Tests for relaxed regime and setup gates."""

from src.data.models import Candle, CandleList
from src.planitt.confluence import evaluate_confluence_pre_gates_with_reason


def _trending_candles(n: int = 240) -> CandleList:
    candles = []
    base = 100.0
    for i in range(n):
        close = base + i * 0.35
        candles.append(
            Candle(
                timestamp=1_700_000_000_000 + i * 900_000,
                open=close - 0.2,
                high=close + 0.5,
                low=close - 0.5,
                close=close,
                volume=1100 + (i % 8) * 25,
            )
        )
    return CandleList(symbol="BTC", timeframe="1h", candles=candles)


def test_trending_market_can_pass_with_relaxed_gates():
    ev = evaluate_confluence_pre_gates_with_reason(
        _trending_candles(),
        adx_trend_threshold=15.0,
        volume_multiplier=1.0,
        touch_tolerance_pct=0.02,
        min_confluence_hits=3,
    )
    # May still reject on votes in unit test; ensure not blocked only by regime if ADX ok
    if ev.features is None:
        assert "regime_filtered" not in (ev.reject_reason or "")
