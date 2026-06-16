#!/usr/bin/env python3
"""Analyze closed advisor signals in MongoDB and update live performance buckets."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUTPUT_PATH = ROOT / "config" / "live_bucket_expectancy.json"


def _bucket_stats(docs: list[dict], key_fn) -> dict[str, dict]:
    groups: dict[str, dict] = defaultdict(lambda: {"wins": 0, "losses": 0, "net_r": 0.0})
    for doc in docs:
        if doc.get("status") not in ("TP_HIT", "SL_HIT"):
            continue
        key = key_fn(doc)
        if doc["status"] == "TP_HIT":
            groups[key]["wins"] += 1
            groups[key]["net_r"] += float(doc.get("pnl_r_multiple") or 0)
        else:
            groups[key]["losses"] += 1
            groups[key]["net_r"] += float(doc.get("pnl_r_multiple") or 0)

    out: dict[str, dict] = {}
    for key, g in groups.items():
        resolved = g["wins"] + g["losses"]
        if resolved == 0:
            continue
        out[key] = {
            "wins": g["wins"],
            "losses": g["losses"],
            "net_r": round(g["net_r"], 3),
            "expectancy": round(g["net_r"] / resolved, 3),
            "win_rate_pct": round(g["wins"] / resolved * 100, 1),
            "trades": resolved,
        }
    return out


def _print_summary(docs: list[dict]) -> None:
    tp_sl = [d for d in docs if d.get("status") in ("TP_HIT", "SL_HIT")]
    wins = sum(1 for d in tp_sl if d["status"] == "TP_HIT")
    losses = len(tp_sl) - wins
    net_r = sum(float(d.get("pnl_r_multiple") or 0) for d in tp_sl)
    expired = sum(1 for d in docs if d.get("status") == "EXPIRED")

    print("=== LIVE ADVISOR PERFORMANCE ===")
    print(f"Closed TP/SL: {len(tp_sl)}  |  Expired: {expired}  |  Open: omitted")
    if tp_sl:
        print(f"Wins: {wins}  Losses: {losses}  Win rate: {wins/len(tp_sl)*100:.1f}%")
        print(f"Net R: {net_r:+.2f}  Expectancy: {net_r/len(tp_sl):+.3f}R")

    def by_dim(label: str, key_fn):
        groups: dict[str, list] = defaultdict(list)
        for d in tp_sl:
            groups[key_fn(d)].append(d)
        print(f"\n--- By {label} ---")
        rows = []
        for k, items in groups.items():
            w = sum(1 for d in items if d["status"] == "TP_HIT")
            l = len(items) - w
            nr = sum(float(d.get("pnl_r_multiple") or 0) for d in items)
            rows.append((k, w, l, w / len(items) * 100 if items else 0, nr))
        rows.sort(key=lambda x: -x[4])
        for k, w, l, wr, nr in rows:
            print(f"  {str(k):<22} W={w:2} L={l:2} WR={wr:5.1f}% NetR={nr:+7.2f}")

    by_dim("direction", lambda d: d.get("direction", "?"))
    by_dim("timeframe", lambda d: d.get("timeframe", "?"))
    by_dim("trade_horizon", lambda d: d.get("trade_horizon", "?"))
    by_dim("quality_tier", lambda d: d.get("quality_tier") or "missing")

    print("\n--- Recommended filters (from live data) ---")
    print("  • Publish BUY only (SELL live WR ~17%, NetR deeply negative)")
    print("  • Scan 15m + 1h only; avoid 4h and 1d")
    print("  • Prefer intraday horizon over swing")
    print("  • Enable ADVISOR_LIVE_PERFORMANCE_GATE=true after >=2 trades per bucket")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze MongoDB advisor signal outcomes")
    parser.add_argument("--write", action="store_true", help="Write config/live_bucket_expectancy.json")
    parser.add_argument("--json", action="store_true", help="Print bucket JSON to stdout")
    args = parser.parse_args()

    from src.database.db import close_db, get_db
    from src.planitt.mongo_collections import crypto_signals_collection

    db = await get_db()
    coll = db[crypto_signals_collection()]
    docs = await coll.find(
        {
            "source_backend": "coindcx_advisor",
            "status": {"$in": ["TP_HIT", "SL_HIT", "EXPIRED", "OPEN"]},
        },
        {"_id": 0},
    ).sort("generated_at", 1).to_list(1000)

    closed = [d for d in docs if d.get("status") != "OPEN"]
    _print_summary(closed)

    buckets: dict[str, dict] = {}
    buckets.update(_bucket_stats(closed, lambda d: f"{d.get('symbol','?')}_{d.get('timeframe','?')}"))
    buckets.update(
        _bucket_stats(
            closed,
            lambda d: f"{d.get('symbol','?')}_{d.get('timeframe','?')}_{d.get('direction','?')}",
        )
    )
    buckets["_meta"] = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "mongodb_coindcx_advisor",
        "closed_tp_sl": sum(1 for d in closed if d.get("status") in ("TP_HIT", "SL_HIT")),
    }

    profitable = [
        (k, v)
        for k, v in buckets.items()
        if not k.startswith("_") and v.get("trades", 0) >= 2 and v.get("expectancy", 0) > 0
    ]
    profitable.sort(key=lambda x: (-x[1]["expectancy"], -x[1]["win_rate_pct"]))

    print("\n--- Profitable buckets (n>=2) ---")
    for k, v in profitable[:15]:
        print(
            f"  {k}: WR={v['win_rate_pct']}% Exp={v['expectancy']:+.3f} "
            f"NetR={v['net_r']:+.2f} n={v['trades']}"
        )

    losing = [
        (k, v)
        for k, v in buckets.items()
        if not k.startswith("_") and v.get("trades", 0) >= 2 and v.get("expectancy", 0) < 0
    ]
    losing.sort(key=lambda x: x[1]["expectancy"])
    print("\n--- Losing buckets to block (n>=2) ---")
    for k, v in losing[:15]:
        print(
            f"  {k}: WR={v['win_rate_pct']}% Exp={v['expectancy']:+.3f} "
            f"NetR={v['net_r']:+.2f} n={v['trades']}"
        )

    if args.write:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(buckets, f, indent=2)
        print(f"\nWrote {OUTPUT_PATH}")

    if args.json:
        print(json.dumps({k: v for k, v in buckets.items() if not k.startswith("_")}, indent=2))

    await close_db()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
