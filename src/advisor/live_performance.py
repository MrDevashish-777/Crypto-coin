"""Live signal performance buckets — derived from closed MongoDB advisor trades."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LIVE_BUCKET_PATH = Path("config/live_bucket_expectancy.json")


@lru_cache(maxsize=1)
def load_live_bucket_expectancy() -> dict[str, dict[str, float]]:
    if not LIVE_BUCKET_PATH.exists():
        return {}
    try:
        with open(LIVE_BUCKET_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("Could not load live bucket expectancy: %s", exc)
        return {}


def live_bucket_key(symbol: str, timeframe: str, direction: str | None = None) -> str:
    sym = symbol.upper()
    tf = timeframe
    if direction:
        return f"{sym}_{tf}_{direction.upper()}"
    return f"{sym}_{tf}"


def get_live_bucket_expectancy(
    symbol: str,
    timeframe: str,
    *,
    direction: str | None = None,
) -> float | None:
    buckets = load_live_bucket_expectancy()
    if direction:
        entry = buckets.get(live_bucket_key(symbol, timeframe, direction))
        if entry is not None:
            return float(entry.get("expectancy", 0))
    entry = buckets.get(live_bucket_key(symbol, timeframe))
    if entry is None:
        return None
    return float(entry.get("expectancy", 0))


def passes_live_bucket(
    symbol: str,
    timeframe: str,
    *,
    direction: str | None = None,
    min_expectancy: float = 0.0,
    min_trades: int = 2,
) -> tuple[bool, str | None]:
    """Reject when live history shows negative expectancy with enough samples."""
    buckets = load_live_bucket_expectancy()
    key = live_bucket_key(symbol, timeframe, direction) if direction else live_bucket_key(symbol, timeframe)
    entry = buckets.get(key)
    if not entry:
        return True, None
    trades = int(entry.get("trades", 0))
    if trades < min_trades:
        return True, None
    exp = float(entry.get("expectancy", 0))
    if exp < min_expectancy:
        return False, f"live_bucket_{key}_{exp:.3f}"
    return True, None


def summarize_buckets(buckets: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, entry in buckets.items():
        if not isinstance(entry, dict):
            continue
        trades = int(entry.get("trades", 0))
        wins = int(entry.get("wins", 0))
        losses = int(entry.get("losses", 0))
        resolved = wins + losses
        wr = wins / resolved * 100 if resolved else 0.0
        rows.append(
            {
                "key": key,
                "wins": wins,
                "losses": losses,
                "win_rate_pct": round(wr, 1),
                "net_r": round(float(entry.get("net_r", 0)), 2),
                "expectancy": round(float(entry.get("expectancy", 0)), 3),
                "trades": trades,
            }
        )
    rows.sort(key=lambda r: (-r["expectancy"], -r["win_rate_pct"]))
    return rows
