import asyncio
from datetime import datetime, timezone
import logging
from src.advisor.schemas import AdvisorSignal
from src.execution.executor import executor

logging.basicConfig(level=logging.INFO)

async def test_exec():
    signal = AdvisorSignal(
        symbol="ADA",
        pair="B-BTC_USDT",
        margin_currency="USDT",
        timeframe="15m",
        direction="BUY",
        entry_low=60000.0,
        entry_high=60500.0,
        stop_loss=59000.0,
        target=65000.0,
        sl_pct=1.0,
        tp_pct=5.0,
        leverage=20.0,
        risk_reward="1:5.0",
        confidence=0.85,
        valid_until_ist=datetime.now(timezone.utc),
        generated_at=datetime.now(timezone.utc),
        live_price_at_signal=60200.0,
        indicators=["ADX", "EMA"],
        setup_type="volume_breakout",
        confluence_hits=[],
        trade_horizon="intraday",
        reason_why_token="Testing",
        reason_entry="Testing",
        reason_monitor="Testing"
    )
    await executor.execute_signal(signal)
    await executor.close()

asyncio.run(test_exec())
