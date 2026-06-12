#!/usr/bin/env python3
"""Walk-forward optimizer for advisor gate thresholds."""

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

from src.analysis.backtest_engine import BacktestEngine, BacktestGateConfig, BacktestResult
from src.data.historical_loader import default_backtest_range, load_or_fetch_candles
from src.data.models import CandleList
from src.planitt.mtf_confluence import higher_timeframes_for

RECOMMENDED_ENV_PATH = Path("config/backtest_recommended.env")
REPORT_PATH = Path("config/backtest_optimization_report.json")
BUCKET_REPORT_PATH = Path("config/backtest_bucket_expectancy.json")


def _split_indices(n: int, train_ratio: float) -> tuple[int, int]:
    train_end = int(n * train_ratio)
    return train_end, n


def _score_result(
    result: BacktestResult,
    *,
    min_win_rate: float,
    min_signals_per_week: float,
) -> float:
    closed = result.wins + result.losses
    if closed < 3:
        return -999.0
    if result.win_rate < min_win_rate * 100.0:
        return -500.0 + result.expectancy
    if result.signals_per_week < min_signals_per_week:
        return -300.0 + result.expectancy
    return result.expectancy


def _grid_configs() -> list[BacktestGateConfig]:
    adx_values = [18.0, 20.0, 22.0, 25.0, 28.0]
    hit_values = [3, 4, 5]
    conf_values = [0.70, 0.72, 0.75, 0.78, 0.82]
    source_values = [4, 5, 6]
    margin_values = [0.12, 0.15, 0.18, 0.22]

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


async def _load_datasets(
    symbols: list[str],
    timeframes: list[str],
    start: datetime,
    end: datetime,
    cache_dir: Path,
) -> list[tuple[CandleList, dict[str, CandleList] | None]]:
    datasets: list[tuple[CandleList, dict[str, CandleList] | None]] = []
    for symbol in symbols:
        for timeframe in timeframes:
            cl = await load_or_fetch_candles(symbol, timeframe, start, end, cache_dir=cache_dir)
            if len(cl.candles) < 300:
                continue
            htf: dict[str, CandleList] = {}
            for tf in higher_timeframes_for(timeframe):
                htf_cl = await load_or_fetch_candles(symbol, tf, start, end, cache_dir=cache_dir)
                if htf_cl.candles:
                    htf[tf] = htf_cl
            datasets.append((cl, htf or None))
    return datasets


def _run_wfo(
    datasets: list[tuple[CandleList, dict[str, CandleList] | None]],
    *,
    window: int,
    forward: int,
    train_ratio: float,
    min_win_rate: float,
    min_signals_per_week: float,
    max_configs: int | None,
) -> dict:
    engine = BacktestEngine(window_size=window, forward_bars=forward, production_parity=True)
    configs = _grid_configs()
    if max_configs:
        configs = configs[:max_configs]

    best_config: BacktestGateConfig | None = None
    best_train_score = -999.0
    train_results: list[dict] = []

    min_bars = min(len(d[0].candles) for d in datasets)
    train_end_idx, _ = _split_indices(min_bars - forward, train_ratio)

    for cfg in configs:
        train_merged = BacktestResult(
            generated_signals=0,
            dropped_windows=0,
            start_at=datetime.now(timezone.utc),
            end_at=datetime.now(timezone.utc),
        )
        train_trades = []
        for candle_list, htf in datasets:
            r = engine.run(
                candle_list,
                gate_config=cfg,
                htf_series=htf,
                end_idx=train_end_idx,
            )
            train_merged.generated_signals += r.generated_signals
            train_merged.dropped_windows += r.dropped_windows
            train_merged.wins += r.wins
            train_merged.losses += r.losses
            train_merged.net_r += r.net_r
            train_trades.extend(r.trades)

        closed = train_merged.wins + train_merged.losses
        train_merged.win_rate = (train_merged.wins / closed * 100.0) if closed else 0.0
        train_merged.expectancy = train_merged.net_r / closed if closed else 0.0
        train_merged.signals_per_week = sum(
            engine.run(c, gate_config=cfg, htf_series=h, end_idx=train_end_idx).signals_per_week
            for c, h in datasets
        ) / max(len(datasets), 1)

        score = _score_result(
            train_merged,
            min_win_rate=min_win_rate,
            min_signals_per_week=min_signals_per_week,
        )
        train_results.append({"config": cfg.merged_with_settings(), "score": score, "train": {
            "signals": train_merged.generated_signals,
            "win_rate_pct": round(train_merged.win_rate, 2),
            "expectancy": round(train_merged.expectancy, 3),
            "net_r": round(train_merged.net_r, 3),
        }})

        if score > best_train_score:
            best_train_score = score
            best_config = cfg

    if best_config is None:
        return {"error": "no_valid_config"}

    oos_wins = 0
    oos_losses = 0
    oos_net_r = 0.0
    oos_trades: list[dict] = []
    bucket_stats: dict[str, dict[str, float]] = {}

    for candle_list, htf in datasets:
        oos_result = engine.run(
            candle_list,
            gate_config=best_config,
            htf_series=htf,
            start_idx=train_end_idx,
        )
        oos_wins += oos_result.wins
        oos_losses += oos_result.losses
        oos_net_r += oos_result.net_r
        oos_trades.extend(oos_result.trades)
        key = f"{candle_list.symbol}_{candle_list.timeframe}"
        bucket_stats[key] = {
            "expectancy": oos_result.expectancy,
            "win_rate_pct": oos_result.win_rate,
            "net_r": oos_result.net_r,
            "trades": oos_result.wins + oos_result.losses,
        }

    oos_closed = oos_wins + oos_losses
    oos_win_rate = (oos_wins / oos_closed * 100.0) if oos_closed else 0.0
    oos_expectancy = oos_net_r / oos_closed if oos_closed else 0.0

    recommended = best_config.merged_with_settings()
    env_lines = [f"{k}={v}" for k, v in recommended.items()]
    env_lines.extend([
        f"# OOS win_rate={oos_win_rate:.1f}% expectancy={oos_expectancy:.3f}",
        f"ADVISOR_BACKTEST_MIN_EXPECTANCY={max(0.0, oos_expectancy * 0.5):.3f}",
    ])

    return {
        "recommended": recommended,
        "train_score": best_train_score,
        "oos": {
            "wins": oos_wins,
            "losses": oos_losses,
            "win_rate_pct": round(oos_win_rate, 2),
            "expectancy": round(oos_expectancy, 3),
            "net_r": round(oos_net_r, 3),
            "trades": oos_closed,
        },
        "bucket_expectancy": bucket_stats,
        "top_train_configs": sorted(train_results, key=lambda x: x["score"], reverse=True)[:5],
        "env_lines": env_lines,
        "trade_log": oos_trades,
    }


async def main_async(args: argparse.Namespace) -> dict:
    if args.from_date:
        start = datetime.fromisoformat(args.from_date).replace(tzinfo=timezone.utc)
    else:
        start, _ = default_backtest_range(args.months)
    if args.to_date:
        end = datetime.fromisoformat(args.to_date).replace(tzinfo=timezone.utc)
    else:
        _, end = default_backtest_range(args.months)

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    timeframes = [t.strip() for t in args.timeframes.split(",") if t.strip()]
    cache_dir = Path(args.cache_dir)

    datasets = await _load_datasets(symbols, timeframes, start, end, cache_dir)
    if not datasets:
        return {"error": "no_datasets_loaded"}

    return _run_wfo(
        datasets,
        window=args.window,
        forward=args.forward,
        train_ratio=args.train_ratio,
        min_win_rate=args.min_win_rate,
        min_signals_per_week=args.min_signals_per_week,
        max_configs=args.max_configs,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward advisor optimizer")
    parser.add_argument("--symbols", default="BTC,ETH,SOL")
    parser.add_argument("--timeframes", default="15m,1h,4h")
    parser.add_argument("--months", type=int, default=6)
    parser.add_argument("--from-date", default=None)
    parser.add_argument("--to-date", default=None)
    parser.add_argument("--window", type=int, default=240)
    parser.add_argument("--forward", type=int, default=48)
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--min-win-rate", type=float, default=0.65)
    parser.add_argument("--min-signals-per-week", type=float, default=3.0)
    parser.add_argument("--max-configs", type=int, default=None)
    parser.add_argument("--cache-dir", default="data/candles")
    parser.add_argument("--write-env", action="store_true")
    args = parser.parse_args()

    report = asyncio.run(main_async(args))

    if args.write_env and "recommended" in report:
        RECOMMENDED_ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
        RECOMMENDED_ENV_PATH.write_text("\n".join(report.get("env_lines", [])) + "\n", encoding="utf-8")
        trade_log = report.pop("trade_log", [])
        REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
        BUCKET_REPORT_PATH.write_text(
            json.dumps(report.get("bucket_expectancy", {}), indent=2),
            encoding="utf-8",
        )
        weights_log = Path("config/backtest_trade_log.json")
        weights_log.write_text(json.dumps(trade_log, indent=2), encoding="utf-8")

    print(json.dumps({k: v for k, v in report.items() if k != "trade_log"}, indent=2))


if __name__ == "__main__":
    main()
