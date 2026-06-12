"""Historical candle fetch + local cache for backtesting."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from config.settings import settings
from src.data.coindcx_client import CoinDCXClient
from src.data.models import Candle, CandleList

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path("data/candles")


def _candle_to_dict(c: Candle) -> dict:
    return {
        "timestamp": c.timestamp,
        "open": c.open,
        "high": c.high,
        "low": c.low,
        "close": c.close,
        "volume": c.volume,
    }


def _candle_from_dict(d: dict) -> Candle:
    return Candle(
        timestamp=int(d["timestamp"]),
        open=float(d["open"]),
        high=float(d["high"]),
        low=float(d["low"]),
        close=float(d["close"]),
        volume=float(d.get("volume", 0) or 0),
    )


def cache_path(
    symbol: str,
    timeframe: str,
    *,
    cache_dir: Path | str = DEFAULT_CACHE_DIR,
    margin_currency: str | None = None,
) -> Path:
    margin = (margin_currency or settings.COINDCX_DEFAULT_MARGIN).upper()
    base = Path(cache_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{symbol.upper()}_{margin}_{timeframe}.json"


def save_candles(candle_list: CandleList, path: Path | str) -> None:
    """Persist CandleList to JSON cache."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "symbol": candle_list.symbol,
        "timeframe": candle_list.timeframe,
        "candles": [_candle_to_dict(c) for c in candle_list.candles],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    logger.info("Saved %d candles to %s", len(candle_list.candles), path)


def load_candles(path: Path | str) -> CandleList | None:
    """Load CandleList from JSON cache; returns None if missing."""
    path = Path(path)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    candles = [_candle_from_dict(d) for d in payload.get("candles", [])]
    return CandleList(
        symbol=payload.get("symbol", "UNKNOWN"),
        timeframe=payload.get("timeframe", "1h"),
        candles=candles,
    )


async def fetch_historical_candles(
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    *,
    margin_currency: str | None = None,
    client: CoinDCXClient | None = None,
) -> CandleList:
    """Fetch paginated historical candles from CoinDCX."""
    margin = (margin_currency or settings.COINDCX_DEFAULT_MARGIN).upper()
    own_client = client is None
    if own_client:
        client = CoinDCXClient()
    assert client is not None

    try:
        pair = client.build_pair(symbol, margin)
        candles = await client.get_klines_range(pair, timeframe, start, end)
        return CandleList(symbol=symbol.upper(), timeframe=timeframe, candles=candles)
    finally:
        if own_client:
            await client.close()


async def load_or_fetch_candles(
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    *,
    cache_dir: Path | str = DEFAULT_CACHE_DIR,
    margin_currency: str | None = None,
    force_refresh: bool = False,
) -> CandleList:
    """
    Load candles from cache when present and covering the requested range;
    otherwise fetch from CoinDCX and write cache.
    """
    path = cache_path(symbol, timeframe, cache_dir=cache_dir, margin_currency=margin_currency)
    if not force_refresh:
        cached = load_candles(path)
        if cached and len(cached.candles) >= 50:
            start_ms = int(start.astimezone(timezone.utc).timestamp() * 1000)
            end_ms = int(end.astimezone(timezone.utc).timestamp() * 1000)
            first_ts = cached.candles[0].timestamp
            last_ts = cached.candles[-1].timestamp
            if first_ts <= start_ms + 86400000 and last_ts >= end_ms - 86400000:
                filtered = [
                    c for c in cached.candles if start_ms <= c.timestamp <= end_ms
                ]
                if len(filtered) >= 50:
                    logger.info("Cache hit %s (%d bars)", path.name, len(filtered))
                    return CandleList(symbol=symbol.upper(), timeframe=timeframe, candles=filtered)

    candle_list = await fetch_historical_candles(
        symbol,
        timeframe,
        start,
        end,
        margin_currency=margin_currency,
    )
    if candle_list.candles:
        save_candles(candle_list, path)
    return candle_list


def default_backtest_range(months: int = 6) -> tuple[datetime, datetime]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=months * 30)
    return start, end
