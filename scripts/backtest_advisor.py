#!/usr/bin/env python3
"""Walk-forward advisor backtest on historical candle CSV or synthetic data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.backtest_engine import BacktestEngine
from src.data.models import Candle, CandleList


def _synthetic_uptrend(n: int = 400) -> CandleList:
    candles = []
    base = 100.0
    for i in range(n):
        close = base + i * 0.5
        candles.append(
            Candle(
                timestamp=1_700_000_000_000 + i * 900_000,
                open=close - 0.3,
                high=close + 0.8,
                low=close - 0.6,
                close=close,
                volume=1200 + (i % 12) * 50,
            )
        )
    return CandleList(symbol="BTC", timeframe="1h", candles=candles)


def main() -> None:
    parser = argparse.ArgumentParser(description="Advisor walk-forward backtest")
    parser.add_argument("--symbol", default="BTC")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--window", type=int, default=240)
    parser.add_argument("--forward", type=int, default=48)
    args = parser.parse_args()

    candle_list = _synthetic_uptrend(450)
    engine = BacktestEngine(window_size=args.window, forward_bars=args.forward)
    result = engine.run(candle_list)

    report = {
        "symbol": args.symbol,
        "timeframe": args.timeframe,
        "generated_signals": result.generated_signals,
        "dropped_windows": result.dropped_windows,
        "wins": result.wins,
        "losses": result.losses,
        "win_rate_pct": round(result.win_rate, 2),
        "avg_r_multiple": round(result.avg_r_multiple, 3),
        "top_reject_reasons": dict(
            sorted(result.reject_reasons.items(), key=lambda x: x[1], reverse=True)[:10]
        ),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
