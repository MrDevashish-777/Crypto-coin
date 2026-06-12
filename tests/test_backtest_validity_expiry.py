from __future__ import annotations

from src.analysis.backtest_engine import BacktestEngine
from src.data.models import Candle, CandleList


def test_expired_trade_not_counted_as_loss() -> None:
    candles = []
    base = 100.0
    for i in range(80):
        close = base + (i * 0.01)
        candles.append(
            Candle(
                timestamp=1_700_000_000_000 + i * 3_600_000,
                open=close,
                high=close + 0.05,
                low=close - 0.05,
                close=close,
                volume=1000,
            )
        )
    cl = CandleList(symbol="BTC", timeframe="1h", candles=candles)
    engine = BacktestEngine(window_size=30, forward_bars=40, production_parity=False)

    valid_until_ms = candles[35].timestamp
    trade = engine._simulate_trade(
        cl,
        35,
        side="BUY",
        entry=100.0,
        stop_loss=90.0,
        target=200.0,
        valid_until_ms=valid_until_ms,
    )
    assert trade.outcome == "expired"
    assert trade.r_multiple == 0.0
