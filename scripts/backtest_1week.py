#!/usr/bin/env python3
"""One-week advisor backtest — production parity or high-volume performance profile."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        import os

        os.environ[key.strip()] = value.strip()


async def _load_htf(symbol: str, tf: str, start, end, cache_dir: Path):
    from src.data.historical_loader import load_or_fetch_candles
    from src.planitt.mtf_confluence import higher_timeframes_for

    htf: dict = {}
    for h in higher_timeframes_for(tf):
        cl = await load_or_fetch_candles(symbol, h, start, end, cache_dir=cache_dir)
        if cl.candles:
            htf[h] = cl
    return htf or None


def _metrics_for_trades(trades: list, label: str, *, risk_pct: float) -> dict:
    closed = [t for t in trades if t.outcome in ("tp_hit", "sl_hit")]
    wins = sum(1 for t in closed if t.outcome == "tp_hit")
    losses = len(closed) - wins
    expired = sum(1 for t in trades if t.outcome == "expired")
    net_r = sum(t.r_multiple for t in closed)
    gross_win = sum(t.r_multiple for t in closed if t.r_multiple > 0)
    gross_loss = abs(sum(t.r_multiple for t in closed if t.r_multiple < 0))
    pf = (gross_win / gross_loss) if gross_loss > 0 else (gross_win if gross_win > 0 else 0.0)
    wr = (wins / len(closed) * 100) if closed else 0.0
    exp = net_r / len(closed) if closed else 0.0
    net_return_pct = net_r * risk_pct
    equity = 100.0
    for t in closed:
        equity *= 1.0 + (t.r_multiple * risk_pct / 100.0)
    compounded_return_pct = equity - 100.0
    return {
        "label": label,
        "signals": len(trades),
        "closed_tp_sl": len(closed),
        "wins": wins,
        "losses": losses,
        "expired": expired,
        "win_rate_pct": round(wr, 2),
        "net_r": round(net_r, 3),
        "expectancy": round(exp, 3),
        "profit_factor": round(pf, 3),
        "net_return_pct": round(net_return_pct, 2),
        "compounded_return_pct": round(compounded_return_pct, 2),
    }


def _first_idx_at_or_after(candles, ts_ms: int) -> int | None:
    for i, c in enumerate(candles):
        if c.timestamp >= ts_ms:
            return i
    return None


async def main() -> int:
    high_volume = "--high-volume" in sys.argv or "-H" in sys.argv
    high_accuracy = "--high-accuracy" in sys.argv or "-A" in sys.argv
    args = [a for a in sys.argv[1:] if a not in ("--high-volume", "-H", "--high-accuracy", "-A")]
    eval_days = int(args[0]) if args else 7

    if high_volume:
        _load_env_file(ROOT / "config" / "high_volume_backtest.env")
    elif high_accuracy:
        _load_env_file(ROOT / "config" / "high_accuracy.env")

    from config.settings import get_settings

    get_settings.cache_clear()
    from config.settings import settings as s  # noqa: reload

    from config.constants import CRYPTO_PAIRS
    from src.analysis.backtest_engine import BacktestEngine, SimulatedTrade
    from src.data.historical_loader import DEFAULT_CACHE_DIR, load_or_fetch_candles

    warmup_days = 180
    end_at = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    eval_start = end_at - timedelta(days=eval_days)
    data_start = end_at - timedelta(days=warmup_days)

    symbols = list(CRYPTO_PAIRS.keys())
    timeframes = s.advisor_scan_timeframes
    cache_dir = DEFAULT_CACHE_DIR
    risk_pct = s.BACKTEST_RISK_PER_TRADE_PCT

    def _window_for(tf: str, n: int) -> int:
        defaults = {"1h": 240, "4h": 120, "1d": 90, "15m": 280}
        need = defaults.get(tf, 200)
        return min(need, max(80, n // 4))

    eval_start_ms = int(eval_start.timestamp() * 1000)
    all_trades: list[SimulatedTrade] = []
    reject_totals: dict[str, int] = {}
    datasets_loaded = 0

    btc_htf: dict = {}
    for h in ("4h", "1d"):
        cl = await load_or_fetch_candles("BTC", h, data_start, end_at, cache_dir=cache_dir)
        if cl.candles:
            btc_htf[h] = cl

    mode = "high_volume" if high_volume else ("high_accuracy" if high_accuracy else "production_parity")
    print(f"Mode:            {mode}")
    print(f"Backtest window: {eval_start.date()} → {end_at.date()} ({eval_days} days)")
    print(f"Data load:       {data_start.date()} → {end_at.date()} (warmup {warmup_days}d)")
    print(f"Timeframes:      {timeframes}")
    print(f"Symbols:         {len(symbols)}")
    print(f"Weekly cap:      {s.MAX_WEEKLY_SIGNALS}")
    print(f"Risk per R:      {risk_pct}%")
    print()

    for symbol in symbols:
        for tf in timeframes:
            candle_list = await load_or_fetch_candles(
                symbol, tf, data_start, end_at, cache_dir=cache_dir
            )
            window = _window_for(tf, len(candle_list.candles))
            forward = {"15m": 64, "1h": 48, "4h": 24, "1d": 14}.get(tf, 48)
            engine = BacktestEngine(
                window_size=window,
                forward_bars=forward,
                simulate_allocation=not high_volume,
                production_parity=True,
                track_open_positions=not high_volume,
            )
            min_bars = window + forward + 10
            if len(candle_list.candles) < min_bars:
                continue
            eval_idx = _first_idx_at_or_after(candle_list.candles, eval_start_ms)
            start_idx = max(window, eval_idx) if eval_idx is not None else window
            htf = await _load_htf(symbol, tf, data_start, end_at, cache_dir)
            result = engine.run(
                candle_list,
                htf_series=htf,
                btc_htf_series=btc_htf or None,
                start_idx=start_idx,
            )
            datasets_loaded += 1
            for reason, count in result.reject_reasons.items():
                reject_totals[reason] = reject_totals.get(reason, 0) + count
            for log in result.trades:
                if log.get("generated_at_ms", 0) >= eval_start_ms:
                    all_trades.append(
                        SimulatedTrade(
                            side=log["side"],
                            entry=0.0,
                            stop_loss=0.0,
                            target=0.0,
                            outcome=log["outcome"],
                            r_multiple=log["r_multiple"],
                            symbol=log["symbol"],
                            timeframe=log["timeframe"],
                            confidence=log["confidence"],
                            composite_score=log["composite_score"],
                            confluence_hits=tuple(log.get("confluence_hits", [])),
                            generated_at_ms=log["generated_at_ms"],
                        )
                    )

    all_trades.sort(key=lambda t: (-t.composite_score, t.generated_at_ms))
    if high_volume and len(all_trades) > s.MAX_WEEKLY_SIGNALS:
        all_trades = sorted(all_trades, key=lambda t: (-t.composite_score, t.generated_at_ms))[
            : s.MAX_WEEKLY_SIGNALS
        ]
        all_trades.sort(key=lambda t: t.generated_at_ms)

    overall = _metrics_for_trades(all_trades, f"{eval_days}d_{mode}", risk_pct=risk_pct)
    by_tf: dict[str, list] = {}
    by_dir: dict[str, list] = {}
    for t in all_trades:
        by_tf.setdefault(t.timeframe, []).append(t)
        by_dir.setdefault(t.side, []).append(t)

    report = {
        "mode": mode,
        "eval_period": {"from": eval_start.isoformat(), "to": end_at.isoformat(), "days": eval_days},
        "config": {
            "scan_timeframes": timeframes,
            "max_weekly_signals": s.MAX_WEEKLY_SIGNALS,
            "max_daily_signals": s.MAX_DAILY_SIGNALS,
            "positive_buckets_only": s.ADVISOR_POSITIVE_BUCKETS_ONLY,
            "allowed_directions": sorted(s.advisor_allowed_directions),
            "risk_per_r_pct": risk_pct,
        },
        "datasets_loaded": datasets_loaded,
        "summary": overall,
        "by_timeframe": {
            k: _metrics_for_trades(v, k, risk_pct=risk_pct) for k, v in sorted(by_tf.items())
        },
        "by_direction": {
            k: _metrics_for_trades(v, k, risk_pct=risk_pct) for k, v in sorted(by_dir.items())
        },
        "top_reject_reasons": dict(sorted(reject_totals.items(), key=lambda x: -x[1])[:15]),
        "trades": [
            {
                "symbol": t.symbol,
                "timeframe": t.timeframe,
                "side": t.side,
                "outcome": t.outcome,
                "r_multiple": round(t.r_multiple, 3),
                "confidence": round(t.confidence, 3),
                "composite_score": round(t.composite_score, 3),
                "at": datetime.fromtimestamp(
                    t.generated_at_ms / 1000, tz=timezone.utc
                ).isoformat(),
            }
            for t in all_trades
        ],
    }

    out_path = ROOT / "config" / "backtest_1week_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "trades"}, indent=2))
    print(f"\nFull trade log: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
