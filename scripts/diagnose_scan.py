#!/usr/bin/env python3
"""Dry-run advisor scan with reject-reason breakdown (no publish)."""

from __future__ import annotations

import asyncio
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings
from src.advisor.processor import AdvisorProcessor


async def main() -> None:
    proc = AdvisorProcessor()
    ok = await proc.data_fetcher.test_connection()
    if not ok:
        print("CoinDCX unreachable")
        sys.exit(1)

    from src.advisor.persistence import expire_stale_open_signals

    expired = await expire_stale_open_signals()
    print(f"Expired stale OPEN signals: {expired}")

    allowlist = settings.advisor_symbol_allowlist
    tfs = settings.advisor_scan_timeframes
    syms = proc._ordered_scan_symbols(list(allowlist) if allowlist else [])
    if allowlist is not None:
        syms = [s for s in syms if s.upper() in allowlist]
    btc_htf = await proc._fetch_btc_htf("")

    rejects: Counter[str] = Counter()
    candidates: list[tuple[float, str, str, str]] = []

    for tf in tfs:
        for sym in syms:
            out = await proc.generate_signal(sym, tf, dry_run=True, btc_htf=btc_htf)
            if out.get("ok"):
                feat = out.get("features")
                side = feat.side if feat else "?"
                score = out.get("composite_score", 0)
                candidates.append((float(score), sym, tf, side))
            else:
                reason = str(out.get("reject_reason", "unknown")).split(":")[0]
                rejects[reason] += 1

    candidates.sort(reverse=True)
    swing_tfs = {"4h", "1d"}
    swing_candidates = [c for c in candidates if c[2] in swing_tfs]
    intraday_candidates = [c for c in candidates if c[2] not in swing_tfs]

    print(f"\n=== DRY SCAN ({len(syms)} symbols × {len(tfs)} TFs) ===")
    print(f"Scan TFs: {', '.join(tfs)}")
    print(f"Blocked TFs: {sorted(settings.advisor_blocked_timeframes) or 'none'}")
    print(f"Swing horizon block: {settings.ADVISOR_BLOCK_SWING_HORIZON}")
    print(f"Candidates passing all gates: {len(candidates)}")
    print(f"  Intraday (15m/1h): {len(intraday_candidates)}")
    print(f"  Swing (4h/1d):     {len(swing_candidates)}")
    print(f"Would publish (top {settings.MAX_PUBLISH_PER_SCAN}): {min(len(candidates), settings.MAX_PUBLISH_PER_SCAN)}")

    if swing_candidates:
        print("\n--- Swing candidates ---")
        for score, sym, tf, side in swing_candidates[:10]:
            print(f"  {score:.3f}  {sym:6} {tf:4} {side}")

    if intraday_candidates:
        print("\n--- Intraday candidates ---")
        for score, sym, tf, side in intraday_candidates[:10]:
            print(f"  {score:.3f}  {sym:6} {tf:4} {side}")

    if candidates and not swing_candidates:
        swing_rejects: Counter[str] = Counter()
        for tf in swing_tfs:
            if tf not in tfs:
                continue
            for sym in syms:
                out = await proc.generate_signal(sym, tf, dry_run=True, btc_htf=btc_htf)
                if not out.get("ok"):
                    reason = str(out.get("reject_reason", "unknown")).split(":")[0]
                    swing_rejects[reason] += 1
        if swing_rejects:
            print("\n--- Swing-only reject reasons (4h/1d) ---")
            for reason, count in swing_rejects.most_common(15):
                print(f"  {count:3}  {reason}")

    if rejects:
        print("\n--- Reject reasons ---")
        for reason, count in rejects.most_common(20):
            print(f"  {count:3}  {reason}")

    await proc.close()


if __name__ == "__main__":
    asyncio.run(main())
