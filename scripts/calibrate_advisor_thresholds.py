#!/usr/bin/env python3
"""Grid-search advisor thresholds on walk-forward backtest data."""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.backtest_engine import BacktestEngine, BacktestGateConfig
from src.data.historical_loader import default_backtest_range, load_or_fetch_candles
from src.data.models import Candle, CandleList
from src.planitt.mtf_confluence import higher_timeframes_for


def _synthetic_uptrend(n: int = 450) -> CandleList:
    candles = []
    base = 100.0
    for i in range(n):
        close = base + i * 0.45
        candles.append(
            Candle(
                timestamp=1_700_000_000_000 + i * 900_000,
                open=close - 0.25,
                high=close + 0.7,
                low=close - 0.5,
                close=close,
                volume=1100 + (i % 15) * 40,
            )
        )
    return CandleList(symbol="BTC", timeframe="1h", candles=candles)


async def _load_data(args: argparse.Namespace) -> tuple[CandleList, dict[str, CandleList]]:
    if args.synthetic:
        return _synthetic_uptrend(), {}

    start, end = default_backtest_range(args.months)
    candle_list = await load_or_fetch_candles(
        args.symbol,
        args.timeframe,
        start,
        end,
        cache_dir=Path(args.cache_dir),
    )
    htf: dict[str, CandleList] = {}
    for tf in higher_timeframes_for(args.timeframe):
        cl = await load_or_fetch_candles(args.symbol, tf, start, end, cache_dir=Path(args.cache_dir))
        if cl.candles:
            htf[tf] = cl
    return candle_list, htf


def _run_grid(
    candle_list: CandleList,
    htf_series: dict[str, CandleList],
    *,
    window: int,
    forward: int,
    adx_values: list[float],
    hit_values: list[int],
    conf_values: list[float],
) -> list[dict]:
    engine = BacktestEngine(window_size=window, forward_bars=forward, production_parity=True)
    rows: list[dict] = []

    for adx, hits, conf in itertools.product(adx_values, hit_values, conf_values):
        gate = BacktestGateConfig(
            adx_trend_threshold=adx,
            min_confluence_hits=hits,
            min_confidence=conf,
        )
        result = engine.run(candle_list, gate_config=gate, htf_series=htf_series or None)
        rows.append(
            {
                "PLANITT_ADX_TREND_THRESHOLD": adx,
                "ADVISOR_MIN_CONFLUENCE_HITS": hits,
                "ADVISOR_MIN_CONFIDENCE": conf,
                "backtest_signals": result.generated_signals,
                "backtest_win_rate_pct": round(result.win_rate, 2),
                "backtest_expectancy": round(result.expectancy, 3),
                "backtest_net_r": round(result.net_r, 3),
                "backtest_avg_r": round(result.avg_r_multiple, 3),
                "signals_per_week": round(result.signals_per_week, 2),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Grid-search advisor gate thresholds")
    parser.add_argument("--window", type=int, default=240)
    parser.add_argument("--forward", type=int, default=48)
    parser.add_argument("--symbol", default="BTC")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--months", type=int, default=6)
    parser.add_argument("--cache-dir", default="data/candles")
    parser.add_argument("--synthetic", action="store_true")
    args = parser.parse_args()

    candle_list, htf_series = asyncio.run(_load_data(args))
    adx_values = [20.0, 22.0, 25.0, 28.0]
    hit_values = [3, 4, 5]
    conf_values = [0.70, 0.75, 0.78, 0.82]

    rows = _run_grid(
        candle_list,
        htf_series,
        window=args.window,
        forward=args.forward,
        adx_values=adx_values,
        hit_values=hit_values,
        conf_values=conf_values,
    )

    ranked = sorted(
        rows,
        key=lambda r: (r["backtest_expectancy"], r["backtest_win_rate_pct"], r["backtest_net_r"]),
        reverse=True,
    )
    report = {
        "data_source": "synthetic" if args.synthetic else f"{args.symbol}_{args.timeframe}",
        "recommended": ranked[0] if ranked else {},
        "top_5": ranked[:5],
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
