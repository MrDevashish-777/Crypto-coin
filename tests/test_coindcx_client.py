"""Tests for CoinDCX client parsing."""

from __future__ import annotations

import pytest

from src.data.coindcx_client import (
    CoinDCXClient,
    _aggregate_candles,
    _candle_from_row,
    _parse_pair,
)
from src.data.models import Candle


def test_parse_pair() -> None:
    assert _parse_pair("B-BTC_USDT") == ("BTC", "USDT")
    assert _parse_pair("B-ETH_INR") == ("ETH", "INR")


def test_candle_from_row_ms_timestamp() -> None:
    row = {
        "open": 100.0,
        "high": 105.0,
        "low": 99.0,
        "close": 103.0,
        "volume": 1000.0,
        "time": 1704153600000,
    }
    c = _candle_from_row(row)
    assert c is not None
    assert c.timestamp == 1704153600000
    assert c.close == 103.0


def test_aggregate_candles_groups_of_three() -> None:
    base = [
        Candle(timestamp=i * 300000, open=100 + i, high=101 + i, low=99 + i, close=100.5 + i, volume=10)
        for i in range(6)
    ]
    agg = _aggregate_candles(base, 3)
    assert len(agg) == 2
    assert agg[0].open == base[0].open
    assert agg[0].close == base[2].close
    assert agg[0].volume == 30.0


@pytest.mark.asyncio
async def test_get_klines_parses_response(monkeypatch) -> None:
    async def _fake_fetch(self, pair: str, resolution: str, limit: int) -> list:
        from src.data.models import Candle
        return [
            Candle(
                timestamp=1704153600000,
                open=50000.0,
                high=51000.0,
                low=49500.0,
                close=50500.0,
                volume=100.0,
            )
        ]

    monkeypatch.setattr(CoinDCXClient, "_fetch_rest_candles", _fake_fetch)
    client = CoinDCXClient()
    candles = await client.get_klines("B-BTC_USDT", "1h", limit=10)
    await client.close()
    assert len(candles) == 1
    assert candles[0].close == 50500.0
