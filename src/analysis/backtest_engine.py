from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from config.settings import settings
from src.advisor.targets import compute_advisor_levels
from src.data.models import CandleList
from src.planitt.confluence import evaluate_confluence_pre_gates_with_reason

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    generated_signals: int
    dropped_windows: int
    start_at: datetime
    end_at: datetime
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    avg_r_multiple: float = 0.0
    reject_reasons: dict[str, int] = field(default_factory=dict)


@dataclass
class SimulatedTrade:
    side: str
    entry: float
    stop_loss: float
    target: float
    outcome: str
    r_multiple: float


class BacktestEngine:
    """Walk-forward backtester with simulated TP/SL outcomes."""

    def __init__(self, window_size: int = 240, forward_bars: int = 48) -> None:
        self.window_size = window_size
        self.forward_bars = forward_bars

    def _simulate_trade(
        self,
        candle_list: CandleList,
        start_idx: int,
        *,
        side: str,
        entry: float,
        stop_loss: float,
        target: float,
    ) -> SimulatedTrade:
        end_idx = min(start_idx + self.forward_bars, len(candle_list.candles) - 1)
        outcome = "expired"
        r_multiple = 0.0
        risk = abs(entry - stop_loss)

        for j in range(start_idx + 1, end_idx + 1):
            bar = candle_list.candles[j]
            high, low = bar.high, bar.low
            if side == "BUY":
                if low <= stop_loss:
                    outcome = "sl_hit"
                    r_multiple = -1.0
                    break
                if high >= target:
                    outcome = "tp_hit"
                    r_multiple = abs(target - entry) / max(risk, 1e-9)
                    break
            else:
                if high >= stop_loss:
                    outcome = "sl_hit"
                    r_multiple = -1.0
                    break
                if low <= target:
                    outcome = "tp_hit"
                    r_multiple = abs(entry - target) / max(risk, 1e-9)
                    break

        return SimulatedTrade(
            side=side,
            entry=entry,
            stop_loss=stop_loss,
            target=target,
            outcome=outcome,
            r_multiple=r_multiple,
        )

    def run(self, candle_list: CandleList) -> BacktestResult:
        generated = 0
        dropped = 0
        wins = 0
        losses = 0
        r_multiples: list[float] = []
        reject_reasons: dict[str, int] = {}

        for idx in range(self.window_size, len(candle_list.candles) - self.forward_bars):
            window = CandleList(
                symbol=candle_list.symbol,
                timeframe=candle_list.timeframe,
                candles=candle_list.candles[idx - self.window_size : idx],
            )
            eval_result = evaluate_confluence_pre_gates_with_reason(
                window,
                adx_trend_threshold=settings.PLANITT_ADX_TREND_THRESHOLD,
                volume_multiplier=settings.PLANITT_VOLUME_MULTIPLIER,
                touch_tolerance_pct=settings.PLANITT_TOUCH_TOLERANCE_PCT,
                min_confluence_hits=settings.ADVISOR_MIN_CONFLUENCE_HITS,
            )
            if eval_result.features is None:
                dropped += 1
                reason = (eval_result.reject_reason or "unknown").split(":")[0]
                reject_reasons[reason] = reject_reasons.get(reason, 0) + 1
                continue

            if eval_result.features.pre_confidence < settings.ADVISOR_MIN_CONFIDENCE:
                dropped += 1
                reject_reasons["confidence"] = reject_reasons.get("confidence", 0) + 1
                continue

            levels = compute_advisor_levels(eval_result.features, candle_list=window)
            entry = (float(levels["entry_low"]) + float(levels["entry_high"])) / 2.0
            trade = self._simulate_trade(
                candle_list,
                idx,
                side=eval_result.features.side,
                entry=entry,
                stop_loss=float(levels["stop_loss"]),
                target=float(levels["target"]),
            )
            generated += 1
            if trade.outcome == "tp_hit":
                wins += 1
                r_multiples.append(trade.r_multiple)
            elif trade.outcome == "sl_hit":
                losses += 1
                r_multiples.append(trade.r_multiple)

        start_at = datetime.fromtimestamp(candle_list.candles[0].timestamp / 1000, tz=timezone.utc)
        end_at = datetime.fromtimestamp(candle_list.candles[-1].timestamp / 1000, tz=timezone.utc)
        closed = wins + losses
        win_rate = (wins / closed * 100.0) if closed else 0.0
        avg_r = sum(r_multiples) / len(r_multiples) if r_multiples else 0.0

        logger.info(
            "Backtest %s: generated=%s wins=%s losses=%s win_rate=%.1f%%",
            candle_list.symbol,
            generated,
            wins,
            losses,
            win_rate,
        )
        return BacktestResult(
            generated_signals=generated,
            dropped_windows=dropped,
            start_at=start_at,
            end_at=end_at,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            avg_r_multiple=avg_r,
            reject_reasons=reject_reasons,
        )
