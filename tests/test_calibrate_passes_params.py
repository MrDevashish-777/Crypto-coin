from __future__ import annotations

from src.analysis.backtest_engine import BacktestEngine, BacktestGateConfig
from src.data.models import Candle, CandleList


def _synthetic_mixed(n: int = 400) -> CandleList:
    candles = []
    for i in range(n):
        if i % 40 < 20:
            close = 100.0 + (i % 20) * 0.8
        else:
            close = 116.0 - (i % 20) * 0.6
        candles.append(
            Candle(
                timestamp=1_700_000_000_000 + i * 900_000,
                open=close - 0.4,
                high=close + 0.9,
                low=close - 0.7,
                close=close,
                volume=900 + (i % 10) * 80,
            )
        )
    return CandleList(symbol="BTC", timeframe="1h", candles=candles)


def test_different_gate_configs_change_backtest_output() -> None:
    cl = _synthetic_mixed()
    engine = BacktestEngine(window_size=120, forward_bars=30, production_parity=False)

    loose = BacktestGateConfig(min_confidence=0.50, min_confluence_hits=2, adx_trend_threshold=10.0)
    strict = BacktestGateConfig(min_confidence=0.95, min_confluence_hits=6, adx_trend_threshold=35.0)

    loose_result = engine.run(cl, gate_config=loose)
    strict_result = engine.run(cl, gate_config=strict)

    assert loose_result.generated_signals >= strict_result.generated_signals
    assert loose_result.dropped_windows <= strict_result.dropped_windows
