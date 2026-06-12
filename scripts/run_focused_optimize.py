#!/usr/bin/env python3
"""Focused walk-forward search on stricter gate settings (faster than full grid)."""

from __future__ import annotations

import asyncio
import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.optimize_advisor import (
    BUCKET_REPORT_PATH,
    RECOMMENDED_ENV_PATH,
    REPORT_PATH,
    _run_wfo,
    _score_result,
)
from src.analysis.backtest_engine import BacktestEngine, BacktestGateConfig
from src.data.historical_loader import default_backtest_range, load_or_fetch_candles
from src.planitt.mtf_confluence import higher_timeframes_for


def focused_configs() -> list[BacktestGateConfig]:
    """Search only stricter-than-default gate combinations."""
    adx_values = [22.0, 25.0, 28.0]
    hit_values = [4, 5]
    conf_values = [0.75, 0.78, 0.82, 0.85]
    source_values = [5, 6]
    margin_values = [0.15, 0.18, 0.22]
    configs: list[BacktestGateConfig] = []
    for adx, hits, conf, sources, margin in itertools.product(
        adx_values, hit_values, conf_values, source_values, margin_values
    ):
        configs.append(
            BacktestGateConfig(
                adx_trend_threshold=adx,
                min_confluence_hits=hits,
                min_confidence=conf,
                min_agreeing_sources=sources,
                min_vote_margin=margin,
            )
        )
    return configs


async def load_datasets(symbols, timeframes, months, cache_dir):
    start, end = default_backtest_range(months)
    datasets = []
    for symbol in symbols:
        for tf in timeframes:
            cl = await load_or_fetch_candles(symbol, tf, start, end, cache_dir=cache_dir)
            if len(cl.candles) < 300:
                continue
            htf = {}
            for htf_tf in higher_timeframes_for(tf):
                htf_cl = await load_or_fetch_candles(symbol, htf_tf, start, end, cache_dir=cache_dir)
                if htf_cl.candles:
                    htf[htf_tf] = htf_cl
            datasets.append((cl, htf or None))
    return datasets


def run_focused_wfo(datasets, *, window, forward, train_ratio, min_win_rate, min_signals_per_week):
    import scripts.optimize_advisor as opt

    original = opt._grid_configs
    opt._grid_configs = focused_configs
    try:
        return _run_wfo(
            datasets,
            window=window,
            forward=forward,
            train_ratio=train_ratio,
            min_win_rate=min_win_rate,
            min_signals_per_week=min_signals_per_week,
            max_configs=None,
        )
    finally:
        opt._grid_configs = original


async def main():
    symbols = ["BTC", "ETH", "SOL"]
    cache_dir = Path("data/candles")
    # Search on 4h (fast); validate winner on 1h+4h below
    search_datasets = await load_datasets(symbols, ["4h"], 6, cache_dir)
    report = run_focused_wfo(
        search_datasets,
        window=240,
        forward=48,
        train_ratio=0.70,
        min_win_rate=0.50,
        min_signals_per_week=1.0,
    )

    if "recommended" in report:
        RECOMMENDED_ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
        RECOMMENDED_ENV_PATH.write_text("\n".join(report.get("env_lines", [])) + "\n", encoding="utf-8")
        trade_log = report.pop("trade_log", [])
        REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
        BUCKET_REPORT_PATH.write_text(
            json.dumps(report.get("bucket_expectancy", {}), indent=2), encoding="utf-8"
        )
        Path("config/backtest_trade_log.json").write_text(json.dumps(trade_log, indent=2), encoding="utf-8")

    # Validate recommended config on full 1h+4h portfolio
    if "recommended" in report:
        from src.analysis.backtest_engine import BacktestEngine, BacktestGateConfig

        val_datasets = await load_datasets(symbols, ["1h", "4h"], 6, cache_dir)
        rec = report["recommended"]
        gate = BacktestGateConfig(
            adx_trend_threshold=rec["PLANITT_ADX_TREND_THRESHOLD"],
            min_confluence_hits=int(rec["ADVISOR_MIN_CONFLUENCE_HITS"]),
            min_confidence=rec["ADVISOR_MIN_CONFIDENCE"],
            min_agreeing_sources=int(rec["ADVISOR_MIN_AGREEING_SOURCES"]),
            min_vote_margin=rec["ADVISOR_MIN_VOTE_MARGIN"],
        )
        engine = BacktestEngine(window_size=240, forward_bars=48, simulate_allocation=True, production_parity=True)
        baseline = engine.run_portfolio(val_datasets)
        optimized = engine.run_portfolio(val_datasets, gate_config=gate)
        report["validation_production_like"] = {
            "baseline": {
                "win_rate_pct": round(baseline.win_rate, 2),
                "net_r": round(baseline.net_r, 3),
                "expectancy": round(baseline.expectancy, 3),
                "wins": baseline.wins,
                "losses": baseline.losses,
                "signals_per_week": round(baseline.signals_per_week, 2),
            },
            "optimized": {
                "win_rate_pct": round(optimized.win_rate, 2),
                "net_r": round(optimized.net_r, 3),
                "expectancy": round(optimized.expectancy, 3),
                "wins": optimized.wins,
                "losses": optimized.losses,
                "signals_per_week": round(optimized.signals_per_week, 2),
            },
        }
        REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps({k: v for k, v in report.items() if k != "trade_log"}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
