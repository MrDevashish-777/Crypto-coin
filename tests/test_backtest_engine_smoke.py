from __future__ import annotations

from src.analysis.backtest_engine import BacktestEngine
from src.data.models import Candle, CandleList


def test_backtest_engine_runs_on_synthetic_data() -> None:
    candles = []
    base = 100.0
    for idx in range(320):
        close = base + (idx * 0.2)
        candles.append(
            Candle(
                timestamp=1_700_000_000_000 + (idx * 60_000),
                open=close - 0.3,
                high=close + 0.7,
                low=close - 0.8,
                close=close,
                volume=1000 + idx,
            )
        )
    cl = CandleList(symbol="BTC", timeframe="5m", candles=candles)
    engine = BacktestEngine(window_size=220)
    result = engine.run(cl)
    assert result.generated_signals >= 0
    assert result.dropped_windows >= 0
