"""Data Fetcher — CoinDCX futures OHLCV with caching."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from config.constants import CRYPTO_PAIRS, MIN_CANDLES_FOR_ANALYSIS, TIMEFRAMES
from config.settings import settings
from src.data.coindcx_client import CoinDCXAPIError, CoinDCXClient
from src.data.models import CandleList

logger = logging.getLogger(__name__)


class DataFetcher:
    """Centralized CoinDCX futures market data fetcher."""

    def __init__(self, margin_currency: str | None = None) -> None:
        self.coindcx = CoinDCXClient()
        self.margin_currency = (margin_currency or settings.COINDCX_DEFAULT_MARGIN).upper()
        self.candle_cache: dict[str, CandleList] = {}
        self.last_fetch_time: dict[str, float] = {}
        self.min_candles = MIN_CANDLES_FOR_ANALYSIS
        logger.info("DataFetcher initialized (CoinDCX margin=%s)", self.margin_currency)

    def pair_for_symbol(self, symbol: str, margin_currency: str | None = None) -> str:
        margin = (margin_currency or self.margin_currency).upper()
        if symbol not in CRYPTO_PAIRS:
            raise ValueError(f"Unsupported symbol: {symbol}")
        return self.coindcx.build_pair(symbol, margin)

    async def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
        from_cache: bool = True,
        min_candles: int | None = None,
        margin_currency: str | None = None,
    ) -> CandleList:
        if symbol not in CRYPTO_PAIRS:
            raise ValueError(f"Unsupported symbol: {symbol}")
        if timeframe not in TIMEFRAMES:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        margin = (margin_currency or self.margin_currency).upper()
        cache_key = f"{symbol}_{timeframe}_{margin}"
        required = min_candles if min_candles is not None else self.min_candles.get(timeframe, 50)

        if from_cache and cache_key in self.candle_cache:
            cached = self.candle_cache[cache_key]
            if len(cached) >= required:
                logger.debug("Using cached data for %s", cache_key)
                return cached

        pair = self.pair_for_symbol(symbol, margin)
        try:
            candles = await self.coindcx.merge_ws_with_rest(pair, timeframe, limit=limit)
            if len(candles) < required:
                if len(candles) == 0:
                    raise ValueError(f"no_data:{symbol}:{timeframe}")
                raise ValueError(
                    f"Insufficient candles for {timeframe}: {len(candles)} (required: {required})"
                )
            candle_list = CandleList(symbol=symbol, timeframe=timeframe, candles=candles)
            self.candle_cache[cache_key] = candle_list
            self.last_fetch_time[cache_key] = datetime.utcnow().timestamp()
            logger.info("Fetched %d candles for %s %s (%s)", len(candles), symbol, timeframe, pair)
            return candle_list
        except CoinDCXAPIError as exc:
            if "no_data" in str(exc):
                logger.warning("No candle data from CoinDCX for %s %s (%s)", symbol, timeframe, pair)
            else:
                logger.error("CoinDCX API error for %s %s: %s", symbol, timeframe, exc)
            raise

    async def fetch_all_symbols(
        self,
        timeframe: str = "15m",
        limit: int = 100,
        symbols: list[str] | None = None,
    ) -> dict[str, CandleList]:
        targets = symbols or list(CRYPTO_PAIRS.keys())
        logger.info("Fetching candles for %d symbols", len(targets))
        tasks = [self.fetch_candles(sym, timeframe, limit) for sym in targets]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        results: dict[str, CandleList] = {}
        for symbol, result in zip(targets, results_list):
            if isinstance(result, Exception):
                logger.error("Failed to fetch %s: %s", symbol, result)
            else:
                results[symbol] = result
        logger.info("Successfully fetched %d/%d symbols", len(results), len(targets))
        return results

    async def fetch_candles_since(
        self,
        symbol: str,
        timeframe: str,
        since: datetime,
        *,
        margin_currency: str | None = None,
    ) -> CandleList:
        """Fetch OHLCV from a UTC timestamp through now (for signal reconciliation)."""
        if symbol not in CRYPTO_PAIRS:
            raise ValueError(f"Unsupported symbol: {symbol}")
        if timeframe not in TIMEFRAMES:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        margin = (margin_currency or self.margin_currency).upper()
        pair = self.pair_for_symbol(symbol, margin)
        since_utc = since.astimezone(timezone.utc)
        end_utc = datetime.now(timezone.utc)
        candles = await self.coindcx.get_klines_range(pair, timeframe, since_utc, end_utc)
        if not candles:
            raise ValueError(f"no_data_since:{symbol}:{timeframe}")
        return CandleList(symbol=symbol, timeframe=timeframe, candles=candles)

    async def get_current_price(
        self,
        symbol: str,
        margin_currency: str | None = None,
    ) -> float:
        if symbol not in CRYPTO_PAIRS:
            raise ValueError(f"Unsupported symbol: {symbol}")
        pair = self.pair_for_symbol(symbol, margin_currency)
        return await self.coindcx.get_latest_price(pair)

    async def test_connection(self) -> bool:
        try:
            ok = await self.coindcx.ping()
            if ok:
                logger.info("Successfully connected to CoinDCX API")
            else:
                logger.error("Failed to connect to CoinDCX API")
            return ok
        except Exception as exc:
            logger.error("Connection test failed: %s", exc)
            return False

    async def refresh_instruments(self) -> list[str]:
        """Return base symbols available on CoinDCX for configured margin currencies."""
        bases: set[str] = set()
        for margin in settings.coindcx_margin_currencies_list:
            instruments = await self.coindcx.get_active_instruments(margin)
            for inst in instruments:
                bases.add(inst.base)
        return sorted(bases)

    def clear_cache(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> None:
        if symbol and timeframe:
            prefix = f"{symbol}_{timeframe}_"
            for key in list(self.candle_cache):
                if key.startswith(prefix):
                    del self.candle_cache[key]
        elif symbol:
            for key in [k for k in self.candle_cache if k.startswith(f"{symbol}_")]:
                del self.candle_cache[key]
        else:
            self.candle_cache.clear()

    async def close(self) -> None:
        await self.coindcx.close()
        logger.info("DataFetcher closed")
