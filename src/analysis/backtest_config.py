"""Load backtest optimization artifacts for live pipeline gating."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

BUCKET_PATH = Path("config/backtest_bucket_expectancy.json")
TRADE_LOG_PATH = Path("config/backtest_trade_log.json")


@lru_cache(maxsize=1)
def load_bucket_expectancy() -> dict[str, dict[str, float]]:
    if not BUCKET_PATH.exists():
        return {}
    try:
        with open(BUCKET_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("Could not load bucket expectancy: %s", exc)
        return {}


def bucket_key(symbol: str, timeframe: str) -> str:
    return f"{symbol.upper()}_{timeframe}"


def get_bucket_expectancy(symbol: str, timeframe: str) -> float | None:
    buckets = load_bucket_expectancy()
    entry = buckets.get(bucket_key(symbol, timeframe))
    if not entry:
        return None
    return float(entry.get("expectancy", 0))


def load_backtest_trade_log() -> list[dict[str, Any]]:
    if not TRADE_LOG_PATH.exists():
        return []
    try:
        with open(TRADE_LOG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as exc:
        logger.warning("Could not load backtest trade log: %s", exc)
        return []


def quality_tier(composite_score: float) -> str:
    from config.settings import settings

    if composite_score >= settings.ADVISOR_QUALITY_TIER_A_MIN:
        return "A"
    if composite_score >= settings.ADVISOR_QUALITY_TIER_B_MIN:
        return "B"
    return "C"


_TIER_RANK = {"A": 3, "B": 2, "C": 1}


def passes_quality_tier(tier: str, minimum: str) -> bool:
    return _TIER_RANK.get(tier, 0) >= _TIER_RANK.get(minimum.upper(), 2)
