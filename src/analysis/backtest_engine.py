from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from src.data.models import CandleList
from src.planitt.confluence import evaluate_confluence_pre_gates_with_reason
from src.planitt.targets import compute_planitt_targets

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    generated_signals: int
    dropped_windows: int
    start_at: datetime
    end_at: datetime


class BacktestEngine:
    """Simple walk-forward backtester for Planitt pre-gates and target generation."""

    def __init__(self, window_size: int = 240) -> None:
        self.window_size = window_size

    def run(self, candle_list: CandleList) -> BacktestResult:
        generated = 0
        dropped = 0
        for idx in range(self.window_size, len(candle_list.candles)):
            window = CandleList(
                symbol=candle_list.symbol,
                timeframe=candle_list.timeframe,
                candles=candle_list.candles[idx - self.window_size : idx],
            )
            eval_result = evaluate_confluence_pre_gates_with_reason(window)
            if eval_result.features is None:
                dropped += 1
                continue
            _ = compute_planitt_targets(eval_result.features)
            generated += 1
        start_at = datetime.fromtimestamp(candle_list.candles[0].timestamp / 1000, tz=timezone.utc)
        end_at = datetime.fromtimestamp(candle_list.candles[-1].timestamp / 1000, tz=timezone.utc)
        logger.info("Backtest complete symbol=%s generated=%s dropped=%s", candle_list.symbol, generated, dropped)
        return BacktestResult(generated_signals=generated, dropped_windows=dropped, start_at=start_at, end_at=end_at)
