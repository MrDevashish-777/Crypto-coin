#!/usr/bin/env python3
"""Walk-forward advisor backtest on historical CoinDCX candles or cache."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.backtest_engine import BacktestEngine
from src.data.historical_loader import (
    DEFAULT_CACHE_DIR,
    default_backtest_range,
    load_or_fetch_candles,
)
from src.data.models import Candle, CandleList
from src.planitt.mtf_confluence import higher_timeframes_for


def _synthetic_uptrend(n: int = 450) -> CandleList:
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


async def _load_htf_series(
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    cache_dir: Path,
) -> dict[str, CandleList]:
    htf: dict[str, CandleList] = {}
    for tf in higher_timeframes_for(timeframe):
        cl = await load_or_fetch_candles(
            symbol,
            tf,
            start,
            end,
            cache_dir=cache_dir,
        )
        if cl.candles:
            htf[tf] = cl
    return htf


async def _run_backtest(args: argparse.Namespace) -> dict:
    if args.synthetic:
        candle_list = _synthetic_uptrend(450)
        htf_series: dict[str, CandleList] = {}
        start_at = datetime.now(timezone.utc)
        end_at = start_at
    else:
        if args.from_date:
            start_at = datetime.fromisoformat(args.from_date).replace(tzinfo=timezone.utc)
        else:
            start_at, _ = default_backtest_range(args.months)

        if args.to_date:
            end_at = datetime.fromisoformat(args.to_date).replace(tzinfo=timezone.utc)
        else:
            _, end_at = default_backtest_range(args.months)

        cache_dir = Path(args.cache_dir)
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
        timeframes = [t.strip() for t in args.timeframes.split(",") if t.strip()]

        engine = BacktestEngine(
            window_size=args.window,
            forward_bars=args.forward,
            simulate_allocation=args.simulate_allocation,
            production_parity=not args.legacy_mode,
        )

        datasets: list[tuple[CandleList, dict[str, CandleList] | None]] = []
        for symbol in symbols:
            for timeframe in timeframes:
                candle_list = await load_or_fetch_candles(
                    symbol,
                    timeframe,
                    start_at,
                    end_at,
                    cache_dir=cache_dir,
                    force_refresh=args.refresh,
                )
                if len(candle_list.candles) < args.window + args.forward + 10:
                    print(
                        f"Warning: insufficient data for {symbol} {timeframe} "
                        f"({len(candle_list.candles)} bars)",
                        file=sys.stderr,
                    )
                    continue
                htf = await _load_htf_series(symbol, timeframe, start_at, end_at, cache_dir)
                datasets.append((candle_list, htf or None))

        if not datasets:
            return {"error": "no_data_loaded"}

        if len(datasets) == 1:
            result = engine.run(datasets[0][0], htf_series=datasets[0][1])
        else:
            result = engine.run_portfolio(datasets)

        report = {
            "symbols": symbols,
            "timeframes": timeframes,
            "from": start_at.isoformat(),
            "to": end_at.isoformat(),
            "generated_signals": result.generated_signals,
            "dropped_windows": result.dropped_windows,
            "entry_unfilled": result.entry_unfilled,
            "expired_count": result.expired_count,
            "wins": result.wins,
            "losses": result.losses,
            "win_rate_pct": round(result.win_rate, 2),
            "expectancy": round(result.expectancy, 3),
            "net_r": round(result.net_r, 3),
            "profit_factor": round(result.profit_factor, 3),
            "avg_r_multiple": round(result.avg_r_multiple, 3),
            "signals_per_week": round(result.signals_per_week, 2),
            "max_drawdown_r": round(result.max_drawdown_r, 3),
            "by_symbol": result.by_symbol,
            "by_timeframe": result.by_timeframe,
            "top_reject_reasons": dict(
                sorted(result.reject_reasons.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
        }
        if args.trade_log:
            report["trades"] = result.trades
        return report

    engine = BacktestEngine(
        window_size=args.window,
        forward_bars=args.forward,
        production_parity=not args.legacy_mode,
    )
    result = engine.run(candle_list, htf_series=htf_series)
    return {
        "mode": "synthetic",
        "symbol": args.symbol,
        "timeframe": args.timeframe,
        "generated_signals": result.generated_signals,
        "wins": result.wins,
        "losses": result.losses,
        "win_rate_pct": round(result.win_rate, 2),
        "expectancy": round(result.expectancy, 3),
        "net_r": round(result.net_r, 3),
        "top_reject_reasons": dict(
            sorted(result.reject_reasons.items(), key=lambda x: x[1], reverse=True)[:10]
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Advisor walk-forward backtest")
    parser.add_argument("--symbol", default="BTC")
    parser.add_argument("--symbols", default="BTC,ETH,SOL")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--timeframes", default="15m,1h,4h")
    parser.add_argument("--from-date", default=None, help="ISO date YYYY-MM-DD")
    parser.add_argument("--to-date", default=None, help="ISO date YYYY-MM-DD")
    parser.add_argument("--months", type=int, default=6)
    parser.add_argument("--window", type=int, default=240)
    parser.add_argument("--forward", type=int, default=48)
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--refresh", action="store_true", help="Force re-fetch from CoinDCX")
    parser.add_argument("--synthetic", action="store_true", help="Use synthetic uptrend data")
    parser.add_argument("--legacy-mode", action="store_true", help="Skip MTF/SOP parity gates")
    parser.add_argument("--simulate-allocation", action="store_true")
    parser.add_argument("--trade-log", action="store_true")
    parser.add_argument("--output", default=None, help="Write JSON report to file")
    args = parser.parse_args()

    report = asyncio.run(_run_backtest(args))
    text = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
