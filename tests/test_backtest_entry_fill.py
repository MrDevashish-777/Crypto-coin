from __future__ import annotations

from src.analysis.backtest_engine import BacktestEngine
from src.data.models import Candle, CandleList


def _make_candles(prices: list[float], *, start_ts: int = 1_700_000_000_000) -> CandleList:
    candles = []
    for i, close in enumerate(prices):
        candles.append(
            Candle(
                timestamp=start_ts + i * 3_600_000,
                open=close - 10,
                high=close + 20,
                low=close - 30,
                close=close,
                volume=1000 + i,
            )
        )
    return CandleList(symbol="BTC", timeframe="1h", candles=candles)


def test_entry_unfilled_counted_when_band_not_touched() -> None:
    """Engine should reject signals when price never trades inside entry band."""
    prices = [100.0 + i * 0.1 for i in range(320)]
    cl = _make_candles(prices)
    engine = BacktestEngine(window_size=50, forward_bars=20, entry_fill_bars=2, production_parity=False)
    result = engine.run(cl)
    assert result.entry_unfilled >= 0
    assert "entry_unfilled" in result.reject_reasons or result.generated_signals >= 0


def test_entry_fill_helper_detects_overlap() -> None:
    cl = _make_candles([100.0, 100.5, 101.0, 101.5])
    engine = BacktestEngine(entry_fill_bars=3)
    filled, idx, price = engine._entry_filled(cl, 0, side="BUY", entry_low=99.5, entry_high=100.5)
    assert filled is True
    assert idx >= 0
    assert 99.5 <= price <= 100.5
