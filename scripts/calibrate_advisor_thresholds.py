#!/usr/bin/env python3
"""Grid-search advisor thresholds on walk-forward backtest data."""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
from dataclasses import asdict

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config.settings import settings
from src.analysis.backtest_engine import BacktestEngine
from src.data.models import Candle, CandleList
from src.planitt.confluence import evaluate_confluence_pre_gates_with_reason


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


def _count_passes(
    candle_list: CandleList,
    *,
    adx: float,
    min_hits: int,
    min_conf: float,
    window: int,
) -> tuple[int, int]:
    passes = 0
    total = 0
    for idx in range(window, len(candle_list.candles)):
        window_cl = CandleList(
            symbol=candle_list.symbol,
            timeframe=candle_list.timeframe,
            candles=candle_list.candles[idx - window : idx],
        )
        total += 1
        ev = evaluate_confluence_pre_gates_with_reason(
            window_cl,
            adx_trend_threshold=adx,
            volume_multiplier=settings.PLANITT_VOLUME_MULTIPLIER,
            touch_tolerance_pct=settings.PLANITT_TOUCH_TOLERANCE_PCT,
            min_confluence_hits=min_hits,
        )
        if ev.features is not None and ev.features.pre_confidence >= min_conf:
            passes += 1
    return passes, total


def main() -> None:
    parser = argparse.ArgumentParser(description="Grid-search advisor gate thresholds")
    parser.add_argument("--window", type=int, default=240)
    parser.add_argument("--forward", type=int, default=48)
    args = parser.parse_args()

    candle_list = _synthetic_uptrend()
    adx_values = [20.0, 22.0, 25.0, 28.0]
    hit_values = [3, 4, 5]
    conf_values = [0.70, 0.75, 0.78, 0.82]

    rows: list[dict] = []
    for adx, hits, conf in itertools.product(adx_values, hit_values, conf_values):
        passes, total = _count_passes(
            candle_list,
            adx=adx,
            min_hits=hits,
            min_conf=conf,
            window=args.window,
        )
        engine = BacktestEngine(window_size=args.window, forward_bars=args.forward)
        result = engine.run(candle_list)
        rows.append(
            {
                "PLANITT_ADX_TREND_THRESHOLD": adx,
                "ADVISOR_MIN_CONFLUENCE_HITS": hits,
                "ADVISOR_MIN_CONFIDENCE": conf,
                "gate_pass_rate": round(passes / max(total, 1), 4),
                "backtest_signals": result.generated_signals,
                "backtest_win_rate_pct": round(result.win_rate, 2),
                "backtest_avg_r": round(result.avg_r_multiple, 3),
            }
        )

    ranked = sorted(
        rows,
        key=lambda r: (r["backtest_win_rate_pct"], r["backtest_avg_r"], -r["gate_pass_rate"]),
        reverse=True,
    )
    report = {
        "recommended": ranked[0] if ranked else {},
        "top_5": ranked[:5],
        "note": "Run on real CoinDCX candle export for production calibration.",
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
