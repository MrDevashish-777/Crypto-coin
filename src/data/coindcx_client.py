"""CoinDCX Futures market data client (REST + optional WebSocket buffer)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import aiohttp

from config.constants import COINDCX_REST_RESOLUTION, TIMEFRAME_SECONDS
from config.settings import settings
from src.data.models import Candle

logger = logging.getLogger(__name__)

PUBLIC_BASE = "https://public.coindcx.com"
API_BASE = "https://api.coindcx.com"
CANDLES_PATH = "/market_data/candlesticks"
ACTIVE_INSTRUMENTS_PATH = "/exchange/v1/derivatives/futures/data/active_instruments"


class CoinDCXAPIError(Exception):
    """Raised when CoinDCX API returns an error or unexpected payload."""


@dataclass
class FuturesInstrument:
    """Active CoinDCX futures instrument."""

    pair: str
    margin_currency: str
    base: str


def _parse_pair(pair: str) -> tuple[str, str]:
    """Parse B-BTC_USDT -> (BTC, USDT)."""
    raw = pair.replace("B-", "", 1) if pair.startswith("B-") else pair
    if "_" in raw:
        base, quote = raw.split("_", 1)
        return base.upper(), quote.upper()
    return raw.upper(), "USDT"


def _candle_from_row(row: dict[str, Any]) -> Candle | None:
    ts = row.get("time")
    if ts is None:
        return None
    ts_ms = int(ts) if int(ts) > 10_000_000_000 else int(ts) * 1000
    try:
        candle = Candle(
            timestamp=ts_ms,
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row.get("volume", 0) or 0),
        )
    except (KeyError, TypeError, ValueError):
        return None
    if candle.open <= 0 or candle.high <= 0 or candle.low <= 0 or candle.close <= 0:
        return None
    if candle.high < candle.low:
        return None
    return candle


def _aggregate_candles(candles: list[Candle], group_size: int) -> list[Candle]:
    """Aggregate N consecutive candles into one OHLCV bar."""
    if group_size <= 1:
        return candles
    out: list[Candle] = []
    for i in range(0, len(candles), group_size):
        chunk = candles[i : i + group_size]
        if len(chunk) < group_size:
            continue
        out.append(
            Candle(
                timestamp=chunk[0].timestamp,
                open=chunk[0].open,
                high=max(c.high for c in chunk),
                low=min(c.low for c in chunk),
                close=chunk[-1].close,
                volume=sum(c.volume for c in chunk),
            )
        )
    return out


@dataclass
class CoinDCXClient:
    """Async CoinDCX public futures market data client."""

    _session: aiohttp.ClientSession | None = field(default=None, repr=False)
    _request_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    _last_request_ts: float = field(default=0.0, repr=False)
    _min_request_interval_s: float = 0.12
    _instruments_cache: dict[str, list[FuturesInstrument]] = field(default_factory=dict, repr=False)
    _ws_buffers: dict[str, list[Candle]] = field(default_factory=dict, repr=False)

    async def _init_session(self) -> None:
        if self._session is None:
            timeout = aiohttp.ClientTimeout(connect=5.0, total=30.0)
            self._session = aiohttp.ClientSession(timeout=timeout)

    async def _throttle(self) -> None:
        async with self._request_lock:
            now = time.monotonic()
            elapsed = now - self._last_request_ts
            if elapsed < self._min_request_interval_s:
                await asyncio.sleep(self._min_request_interval_s - elapsed)
            self._last_request_ts = time.monotonic()

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def ping(self) -> bool:
        """Health check via active instruments endpoint."""
        try:
            instruments = await self.get_active_instruments("USDT")
            return len(instruments) > 0
        except Exception as exc:
            logger.error("CoinDCX ping failed: %s", exc)
            return False

    async def get_active_instruments(
        self,
        margin_currency: str,
        *,
        refresh: bool = False,
    ) -> list[FuturesInstrument]:
        """Fetch active futures instruments for a margin currency (USDT or INR)."""
        margin = margin_currency.upper()
        if not refresh and margin in self._instruments_cache:
            return self._instruments_cache[margin]

        await self._init_session()
        assert self._session is not None
        url = f"{API_BASE}{ACTIVE_INSTRUMENTS_PATH}"
        params = {"margin_currency_short_name[]": margin}

        await self._throttle()
        async with self._session.get(url, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise CoinDCXAPIError(f"active_instruments failed: {resp.status} {text[:200]}")
            payload = await resp.json()

        pairs: list[str] = []
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, str):
                    pairs.append(item)
                elif isinstance(item, dict) and item.get("pair"):
                    pairs.append(str(item["pair"]))
        elif isinstance(payload, dict):
            pairs = [str(p) for p in payload.get("instruments", payload.get("data", []))]

        instruments = [
            FuturesInstrument(pair=p, margin_currency=margin, base=_parse_pair(p)[0])
            for p in pairs
            if p.startswith("B-")
        ]
        self._instruments_cache[margin] = instruments
        logger.info("Loaded %d CoinDCX futures instruments for %s", len(instruments), margin)
        return instruments

    def build_pair(self, symbol: str, margin_currency: str) -> str:
        """Build CoinDCX pair id e.g. BTC + USDT -> B-BTC_USDT."""
        return f"B-{symbol.upper()}_{margin_currency.upper()}"

    async def get_klines(
        self,
        pair: str,
        timeframe: str,
        limit: int = 300,
        *,
        margin_currency: str | None = None,
    ) -> list[Candle]:
        """
        Fetch futures OHLCV candles for internal timeframe key (15m, 1h, etc.).

        Uses REST where supported; aggregates from lower resolution otherwise.
        """
        if timeframe not in TIMEFRAME_SECONDS:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        rest_res = COINDCX_REST_RESOLUTION.get(timeframe)
        if rest_res is None:
            return await self._fetch_aggregated(pair, timeframe, limit)

        aggregate_factor = 1
        if timeframe == "15m" and rest_res == "5":
            aggregate_factor = 3
        elif timeframe == "4h" and rest_res == "60":
            aggregate_factor = 4

        # REST resolution may be finer than target TF — fetch enough raw bars before aggregating.
        raw_limit = limit * aggregate_factor + (10 if aggregate_factor > 1 else 5)
        candles = await self._fetch_rest_candles(pair, rest_res, raw_limit)

        if aggregate_factor > 1:
            candles = _aggregate_candles(candles, aggregate_factor)

        return candles[-limit:] if len(candles) > limit else candles

    async def _fetch_aggregated(self, pair: str, timeframe: str, limit: int) -> list[Candle]:
        """Aggregate from finest REST resolution available."""
        if timeframe == "15m":
            raw = await self._fetch_rest_candles(pair, "5", limit * 3 + 10)
            return _aggregate_candles(raw, 3)[-limit:]
        if timeframe == "4h":
            raw = await self._fetch_rest_candles(pair, "60", limit * 4 + 10)
            return _aggregate_candles(raw, 4)[-limit:]
        raise ValueError(f"No aggregation path for timeframe {timeframe}")

    async def _fetch_rest_candles(
        self,
        pair: str,
        resolution: str,
        limit: int,
    ) -> list[Candle]:
        await self._init_session()
        assert self._session is not None

        tf_seconds = {
            "1": 60,
            "5": 300,
            "60": 3600,
            "1D": 86400,
        }.get(resolution, 3600)
        now_s = int(datetime.now(timezone.utc).timestamp())
        from_s = now_s - (limit + 5) * tf_seconds

        params = {
            "pair": pair,
            "from": from_s,
            "to": now_s,
            "resolution": resolution,
            "pcode": "f",
        }
        url = f"{PUBLIC_BASE}{CANDLES_PATH}"

        backoff_s = 0.5
        for attempt in range(1, 4):
            await self._throttle()
            try:
                async with self._session.get(url, params=params) as resp:
                    if resp.status == 429:
                        if attempt == 3:
                            raise CoinDCXAPIError("CoinDCX rate limit exceeded")
                        await asyncio.sleep(backoff_s)
                        backoff_s *= 2
                        continue
                    if resp.status >= 500:
                        if attempt == 3:
                            raise CoinDCXAPIError(f"CoinDCX upstream error: {resp.status}")
                        await asyncio.sleep(backoff_s)
                        backoff_s *= 2
                        continue
                    if resp.status != 200:
                        text = await resp.text()
                        raise CoinDCXAPIError(f"CoinDCX candles error {resp.status}: {text[:200]}")

                    body = await resp.json()
            except asyncio.TimeoutError as exc:
                if attempt == 3:
                    raise CoinDCXAPIError("CoinDCX request timeout") from exc
                await asyncio.sleep(backoff_s)
                backoff_s *= 2
                continue

            if isinstance(body, dict) and body.get("s") == "no_data":
                return []

            if isinstance(body, dict) and body.get("s") not in (None, "ok"):
                raise CoinDCXAPIError(f"CoinDCX candle status: {body.get('s')}")

            rows = body.get("data", body) if isinstance(body, dict) else body
            if not isinstance(rows, list):
                raise CoinDCXAPIError("Unexpected candlestick response shape")

            candles: list[Candle] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                c = _candle_from_row(row)
                if c:
                    candles.append(c)
            candles.sort(key=lambda c: c.timestamp)
            logger.debug("Fetched %d candles for %s res=%s", len(candles), pair, resolution)
            return candles

        raise CoinDCXAPIError("Failed after retries")

    async def get_latest_price(self, pair: str) -> float:
        """Return latest close from 1m candles."""
        candles = await self.get_klines(pair, "1m", limit=2)
        if not candles:
            raise CoinDCXAPIError(f"No price data for {pair}")
        return candles[-1].close

    def cache_ws_candle(self, pair: str, timeframe: str, candle: Candle, *, max_bars: int = 500) -> None:
        """Store a websocket candle update in memory buffer."""
        key = f"{pair}:{timeframe}"
        buf = self._ws_buffers.setdefault(key, [])
        if buf and buf[-1].timestamp == candle.timestamp:
            buf[-1] = candle
        else:
            buf.append(candle)
        if len(buf) > max_bars:
            self._ws_buffers[key] = buf[-max_bars:]

    def get_ws_buffer(self, pair: str, timeframe: str) -> list[Candle]:
        return list(self._ws_buffers.get(f"{pair}:{timeframe}", []))

    async def merge_ws_with_rest(
        self,
        pair: str,
        timeframe: str,
        limit: int,
    ) -> list[Candle]:
        """Backfill REST history and overlay latest WS bars if present."""
        rest = await self.get_klines(pair, timeframe, limit=limit)
        ws = self.get_ws_buffer(pair, timeframe)
        if not ws:
            return rest
        merged = {c.timestamp: c for c in rest}
        for c in ws:
            merged[c.timestamp] = c
        out = sorted(merged.values(), key=lambda c: c.timestamp)
        return out[-limit:]
