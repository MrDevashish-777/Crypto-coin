from __future__ import annotations

import json
from pathlib import Path

from src.data.historical_loader import load_candles, save_candles
from src.data.models import Candle, CandleList


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    candles = [
        Candle(timestamp=1_700_000_000_000, open=100, high=101, low=99, close=100.5, volume=50),
        Candle(timestamp=1_700_000_360_000, open=100.5, high=102, low=100, close=101.5, volume=60),
    ]
    cl = CandleList(symbol="BTC", timeframe="1h", candles=candles)
    path = tmp_path / "BTC_USDT_1h.json"
    save_candles(cl, path)

    loaded = load_candles(path)
    assert loaded is not None
    assert loaded.symbol == "BTC"
    assert loaded.timeframe == "1h"
    assert len(loaded.candles) == 2
    assert loaded.candles[0].close == 100.5


def test_fixture_btc_sample_loads() -> None:
    fixture = Path(__file__).parent / "fixtures" / "btc_1h_sample.json"
    with open(fixture, encoding="utf-8") as f:
        payload = json.load(f)
    assert len(payload["candles"]) >= 50
