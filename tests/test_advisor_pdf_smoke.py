"""PDF generation smoke test with mocked chart."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.advisor.schemas import AdvisorSignal
from src.advisor.validity import compute_valid_until, now_ist
from src.data.models import Candle, CandleList


def _sample_signal() -> AdvisorSignal:
    valid = compute_valid_until("intraday", generated_at=now_ist())
    generated = datetime.now(timezone.utc)
    return AdvisorSignal(
        pair="B-BTC_USDT",
        symbol="BTC",
        margin_currency="USDT",
        direction="BUY",
        trade_horizon="intraday",
        timeframe="1h",
        entry_low=50000.0,
        entry_high=50300.0,
        stop_loss=48750.0,
        target=52000.0,
        sl_pct=2.5,
        tp_pct=3.5,
        leverage=8.0,
        risk_reward="1:1.6",
        confidence=0.75,
        valid_until_ist=valid,
        generated_at=generated,
        live_price_at_signal=50100.0,
        indicators=["EMA 50", "RSI 14"],
        setup_type="trend_pullback",
        confluence_hits=["ema_alignment"],
        reason_why_token="BTC relative strength.",
        reason_entry="Pullback to EMA50.",
        reason_monitor="Watch 52000 resistance.",
    )


def _sample_candles() -> CandleList:
    candles = []
    price = 49000.0
    for i in range(220):
        price += 5
        candles.append(
            Candle(
                timestamp=1700000000000 + i * 3600000,
                open=price,
                high=price + 50,
                low=price - 50,
                close=price + 10,
                volume=1000.0,
            )
        )
    return CandleList(symbol="BTC", timeframe="1h", candles=candles)


@pytest.mark.asyncio
async def test_generate_advisor_pdf_smoke(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADVISOR_OUTPUT_DIR", str(tmp_path))
    import importlib
    import config.settings as settings_mod
    importlib.reload(settings_mod)

    signal = _sample_signal()
    candle_list = _sample_candles()
    chart_path = tmp_path / "charts" / "test.png"
    chart_path.parent.mkdir(parents=True)
    try:
        from PIL import Image

        Image.new("RGB", (10, 10), color=(17, 19, 21)).save(chart_path)
    except ImportError:
        pytest.skip("Pillow required for PDF image embed test")

    with patch(
        "src.reports.pdf_report.render_advisor_chart",
        new=AsyncMock(return_value=chart_path),
    ):
        import src.reports.pdf_report as pdf_mod
        importlib.reload(pdf_mod)
        pdf_path, chart = await pdf_mod.generate_advisor_pdf(signal, candle_list)

    assert pdf_path.parent == tmp_path
    assert pdf_path.exists()
    assert pdf_path.suffix == ".pdf"
    assert chart.exists()
