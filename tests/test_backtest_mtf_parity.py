from __future__ import annotations

import json
from pathlib import Path

from src.analysis.backtest_engine import BacktestEngine
from src.data.historical_loader import load_candles
from src.data.models import CandleList


def test_backtest_runs_on_fixture_with_production_parity() -> None:
    fixture = Path(__file__).parent / "fixtures" / "btc_1h_sample.json"
    with open(fixture, encoding="utf-8") as f:
        payload = json.load(f)
    from src.data.historical_loader import _candle_from_dict

    candles = [_candle_from_dict(d) for d in payload["candles"]]
    cl = CandleList(symbol="BTC", timeframe="1h", candles=candles)

    engine = BacktestEngine(window_size=30, forward_bars=10, production_parity=True)
    result = engine.run(cl, htf_series={})
    assert result.dropped_windows >= 0
    assert result.generated_signals >= 0


def test_load_fixture_via_loader(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "btc_1h_sample.json"
    dest = tmp_path / "btc.json"
    dest.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    loaded = load_candles(dest)
    assert loaded is not None
    assert len(loaded.candles) >= 50
