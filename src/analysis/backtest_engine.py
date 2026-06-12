from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Iterator, Optional
from zoneinfo import ZoneInfo

from config.settings import settings
from src.advisor.allocation import WeeklyAllocationTracker
from src.advisor.sop_gates import validate_levels
from src.advisor.targets import compute_advisor_levels
from src.advisor.validity import compute_valid_until, infer_trade_horizon
from src.analysis.backtest_config import get_bucket_expectancy, passes_quality_tier, quality_tier
from src.data.models import Candle, CandleList
from src.planitt.confluence import evaluate_confluence_pre_gates_with_reason
from src.planitt.mtf_confluence import check_htf_alignment, higher_timeframes_for

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class BacktestGateConfig:
    """Overridable gate thresholds for walk-forward optimization."""

    adx_trend_threshold: float | None = None
    min_confluence_hits: int | None = None
    min_confidence: float | None = None
    min_agreeing_sources: int | None = None
    min_vote_margin: float | None = None
    volume_multiplier: float | None = None
    touch_tolerance_pct: float | None = None

    def merged_with_settings(self) -> dict[str, Any]:
        return {
            "PLANITT_ADX_TREND_THRESHOLD": self.adx_trend_threshold
            if self.adx_trend_threshold is not None
            else settings.PLANITT_ADX_TREND_THRESHOLD,
            "ADVISOR_MIN_CONFLUENCE_HITS": self.min_confluence_hits
            if self.min_confluence_hits is not None
            else settings.ADVISOR_MIN_CONFLUENCE_HITS,
            "ADVISOR_MIN_CONFIDENCE": self.min_confidence
            if self.min_confidence is not None
            else settings.ADVISOR_MIN_CONFIDENCE,
            "ADVISOR_MIN_AGREEING_SOURCES": self.min_agreeing_sources
            if self.min_agreeing_sources is not None
            else settings.ADVISOR_MIN_AGREEING_SOURCES,
            "ADVISOR_MIN_VOTE_MARGIN": self.min_vote_margin
            if self.min_vote_margin is not None
            else settings.ADVISOR_MIN_VOTE_MARGIN,
            "PLANITT_VOLUME_MULTIPLIER": self.volume_multiplier
            if self.volume_multiplier is not None
            else settings.PLANITT_VOLUME_MULTIPLIER,
            "PLANITT_TOUCH_TOLERANCE_PCT": self.touch_tolerance_pct
            if self.touch_tolerance_pct is not None
            else settings.PLANITT_TOUCH_TOLERANCE_PCT,
        }


@contextmanager
def apply_gate_config(config: BacktestGateConfig | None) -> Iterator[None]:
    if config is None:
        yield
        return
    overrides = config.merged_with_settings()
    old: dict[str, Any] = {}
    for key, value in overrides.items():
        old[key] = getattr(settings, key)
        setattr(settings, key, value)
    try:
        yield
    finally:
        for key, value in old.items():
            setattr(settings, key, value)


@dataclass
class BacktestResult:
    generated_signals: int
    dropped_windows: int
    start_at: datetime
    end_at: datetime
    wins: int = 0
    losses: int = 0
    expired_count: int = 0
    entry_unfilled: int = 0
    win_rate: float = 0.0
    avg_r_multiple: float = 0.0
    expectancy: float = 0.0
    net_r: float = 0.0
    profit_factor: float = 0.0
    signals_per_week: float = 0.0
    max_drawdown_r: float = 0.0
    sop_win_rate: float = 0.0
    reject_reasons: dict[str, int] = field(default_factory=dict)
    trades: list[dict[str, Any]] = field(default_factory=list)
    by_symbol: dict[str, dict[str, float]] = field(default_factory=dict)
    by_timeframe: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass
class SimulatedTrade:
    side: str
    entry: float
    stop_loss: float
    target: float
    outcome: str
    r_multiple: float
    symbol: str = ""
    timeframe: str = ""
    confidence: float = 0.0
    composite_score: float = 0.0
    confluence_hits: tuple[str, ...] = ()
    generated_at_ms: int = 0


def _slice_htf_at_timestamp(htf: CandleList, signal_ts_ms: int, min_candles: int = 50) -> CandleList | None:
    candles = [c for c in htf.candles if c.timestamp <= signal_ts_ms]
    if len(candles) < min_candles:
        return None
    return CandleList(symbol=htf.symbol, timeframe=htf.timeframe, candles=candles)


def _bar_datetime_utc(ts_ms: int) -> datetime:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)


def _composite_score(pre_confidence: float, mtf_score: float) -> float:
    return pre_confidence + (mtf_score * settings.ADVISOR_MTF_SCORE_WEIGHT)


class BacktestEngine:
    """Production-parity walk-forward backtester with simulated TP/SL outcomes."""

    def __init__(
        self,
        window_size: int = 240,
        forward_bars: int = 48,
        *,
        entry_fill_bars: int = 6,
        simulate_allocation: bool = False,
        production_parity: bool = True,
    ) -> None:
        self.window_size = window_size
        self.forward_bars = forward_bars
        self.entry_fill_bars = entry_fill_bars
        self.simulate_allocation = simulate_allocation
        self.production_parity = production_parity

    def _entry_filled(
        self,
        candle_list: CandleList,
        start_idx: int,
        *,
        side: str,
        entry_low: float,
        entry_high: float,
    ) -> tuple[bool, int, float]:
        low_band, high_band = sorted([entry_low, entry_high])
        for j in range(start_idx, min(start_idx + self.entry_fill_bars, len(candle_list.candles))):
            bar = candle_list.candles[j]
            if low_band <= bar.low <= high_band or low_band <= bar.high <= high_band:
                if low_band <= bar.close <= high_band:
                    return True, j, bar.close
                return True, j, (low_band + high_band) / 2.0
            if bar.low <= high_band and bar.high >= low_band:
                return True, j, (low_band + high_band) / 2.0
        return False, start_idx, (low_band + high_band) / 2.0

    def _simulate_trade(
        self,
        candle_list: CandleList,
        entry_idx: int,
        *,
        side: str,
        entry: float,
        stop_loss: float,
        target: float,
        valid_until_ms: int,
    ) -> SimulatedTrade:
        end_idx = min(entry_idx + self.forward_bars, len(candle_list.candles) - 1)
        outcome = "expired"
        r_multiple = 0.0
        risk = abs(entry - stop_loss)

        for j in range(entry_idx + 1, end_idx + 1):
            bar = candle_list.candles[j]
            if bar.timestamp > valid_until_ms:
                break
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

    def _compute_metrics(
        self,
        *,
        trades: list[SimulatedTrade],
        generated: int,
        dropped: int,
        entry_unfilled: int,
        expired_count: int,
        reject_reasons: dict[str, int],
        candle_list: CandleList,
        start_at: datetime,
        end_at: datetime,
    ) -> BacktestResult:
        wins = sum(1 for t in trades if t.outcome == "tp_hit")
        losses = sum(1 for t in trades if t.outcome == "sl_hit")
        closed = [t for t in trades if t.outcome in ("tp_hit", "sl_hit")]
        r_multiples = [t.r_multiple for t in closed]
        gross_win = sum(r for r in r_multiples if r > 0)
        gross_loss = abs(sum(r for r in r_multiples if r < 0))

        win_rate = (wins / len(closed) * 100.0) if closed else 0.0
        sop_closed = wins + losses + expired_count
        sop_win_rate = (wins / sop_closed * 100.0) if sop_closed else 0.0
        net_r = sum(r_multiples)
        expectancy = net_r / len(closed) if closed else 0.0
        avg_r = expectancy
        profit_factor = (gross_win / gross_loss) if gross_loss > 0 else (gross_win if gross_win > 0 else 0.0)

        duration_days = max((end_at - start_at).total_seconds() / 86400.0, 1.0)
        signals_per_week = len(trades) / duration_days * 7.0

        equity = 0.0
        peak = 0.0
        max_dd = 0.0
        for t in closed:
            equity += t.r_multiple
            peak = max(peak, equity)
            max_dd = max(max_dd, peak - equity)

        trade_logs = [
            {
                "symbol": t.symbol,
                "timeframe": t.timeframe,
                "side": t.side,
                "outcome": t.outcome,
                "r_multiple": t.r_multiple,
                "confidence": t.confidence,
                "composite_score": t.composite_score,
                "confluence_hits": list(t.confluence_hits),
                "generated_at_ms": t.generated_at_ms,
            }
            for t in trades
        ]

        by_symbol: dict[str, dict[str, float]] = {}
        by_timeframe: dict[str, dict[str, float]] = {}
        for t in closed:
            for bucket, key in ((by_symbol, t.symbol), (by_timeframe, t.timeframe)):
                if key not in bucket:
                    bucket[key] = {"wins": 0, "losses": 0, "net_r": 0.0, "trades": 0}
                bucket[key]["trades"] += 1
                bucket[key]["net_r"] += t.r_multiple
                if t.outcome == "tp_hit":
                    bucket[key]["wins"] += 1
                else:
                    bucket[key]["losses"] += 1

        return BacktestResult(
            generated_signals=generated,
            dropped_windows=dropped,
            start_at=start_at,
            end_at=end_at,
            wins=wins,
            losses=losses,
            expired_count=expired_count,
            entry_unfilled=entry_unfilled,
            win_rate=win_rate,
            avg_r_multiple=avg_r,
            expectancy=expectancy,
            net_r=net_r,
            profit_factor=profit_factor,
            signals_per_week=signals_per_week,
            max_drawdown_r=max_dd,
            sop_win_rate=sop_win_rate,
            reject_reasons=reject_reasons,
            trades=trade_logs,
            by_symbol=by_symbol,
            by_timeframe=by_timeframe,
        )

    def run(
        self,
        candle_list: CandleList,
        *,
        gate_config: BacktestGateConfig | None = None,
        htf_series: dict[str, CandleList] | None = None,
        start_idx: int | None = None,
        end_idx: int | None = None,
    ) -> BacktestResult:
        generated = 0
        dropped = 0
        entry_unfilled = 0
        expired_count = 0
        reject_reasons: dict[str, int] = {}
        completed_trades: list[SimulatedTrade] = []
        allocation = WeeklyAllocationTracker() if self.simulate_allocation else None
        cfg = gate_config or BacktestGateConfig()
        gate_values = cfg.merged_with_settings()

        lo = start_idx if start_idx is not None else self.window_size
        hi = end_idx if end_idx is not None else len(candle_list.candles) - self.forward_bars

        with apply_gate_config(cfg):
            for idx in range(lo, hi):
                window = CandleList(
                    symbol=candle_list.symbol,
                    timeframe=candle_list.timeframe,
                    candles=candle_list.candles[idx - self.window_size : idx],
                )
                signal_bar = candle_list.candles[idx]
                live_price = signal_bar.close

                eval_result = evaluate_confluence_pre_gates_with_reason(
                    window,
                    adx_trend_threshold=gate_values["PLANITT_ADX_TREND_THRESHOLD"],
                    volume_multiplier=gate_values["PLANITT_VOLUME_MULTIPLIER"],
                    touch_tolerance_pct=gate_values["PLANITT_TOUCH_TOLERANCE_PCT"],
                    min_confluence_hits=gate_values["ADVISOR_MIN_CONFLUENCE_HITS"],
                )
                if eval_result.features is None:
                    dropped += 1
                    reason = (eval_result.reject_reason or "unknown").split(":")[0]
                    reject_reasons[reason] = reject_reasons.get(reason, 0) + 1
                    continue

                features = eval_result.features

                if self.production_parity:
                    htf_candles: dict[str, CandleList] = {}
                    if htf_series:
                        for tf in higher_timeframes_for(candle_list.timeframe):
                            series = htf_series.get(tf)
                            if series is not None:
                                sliced = _slice_htf_at_timestamp(series, signal_bar.timestamp)
                                if sliced is not None:
                                    htf_candles[tf] = sliced
                    mtf = check_htf_alignment(features.side, candle_list.timeframe, htf_candles)
                    if not mtf.aligned:
                        dropped += 1
                        reason = (mtf.reject_reason or "mtf_misalignment").split(":")[0]
                        reject_reasons[reason] = reject_reasons.get(reason, 0) + 1
                        continue
                    features = replace(features, mtf_score=mtf.mtf_score)

                if features.pre_confidence < gate_values["ADVISOR_MIN_CONFIDENCE"]:
                    dropped += 1
                    reject_reasons["confidence"] = reject_reasons.get("confidence", 0) + 1
                    continue

                if allocation is not None:
                    bar_dt = _bar_datetime_utc(signal_bar.timestamp)
                    can_pub, alloc_reason = allocation.can_publish(candle_list.symbol, now=bar_dt)
                    if not can_pub:
                        dropped += 1
                        reason = (alloc_reason or "allocation").split(":")[0]
                        reject_reasons[reason] = reject_reasons.get(reason, 0) + 1
                        continue

                composite = _composite_score(features.pre_confidence, features.mtf_score)
                tier = quality_tier(composite)
                if composite < settings.ADVISOR_MIN_COMPOSITE_SCORE:
                    dropped += 1
                    reject_reasons["composite_below_min"] = reject_reasons.get("composite_below_min", 0) + 1
                    continue
                if features.mtf_score < settings.ADVISOR_MIN_MTF_SCORE:
                    dropped += 1
                    reject_reasons["mtf_below_min"] = reject_reasons.get("mtf_below_min", 0) + 1
                    continue
                if not passes_quality_tier(tier, settings.ADVISOR_PUBLISH_MIN_QUALITY_TIER):
                    dropped += 1
                    reject_reasons["quality_tier"] = reject_reasons.get("quality_tier", 0) + 1
                    continue
                if settings.ADVISOR_BLOCK_NEGATIVE_BUCKETS:
                    bucket_exp = get_bucket_expectancy(candle_list.symbol, candle_list.timeframe)
                    if bucket_exp is not None and bucket_exp < 0:
                        dropped += 1
                        reject_reasons["negative_bucket"] = reject_reasons.get("negative_bucket", 0) + 1
                        continue

                levels = compute_advisor_levels(
                    features, candle_list=window, live_price=live_price
                )

                if self.production_parity:
                    sop = validate_levels(
                        direction=features.side,
                        entry_low=float(levels["entry_low"]),
                        entry_high=float(levels["entry_high"]),
                        stop_loss=float(levels["stop_loss"]),
                        target=float(levels["target"]),
                        live_price=live_price,
                        sl_pct=float(levels["sl_pct"]),
                        tp_pct=float(levels["tp_pct"]),
                        leverage=float(levels["leverage"]),
                        risk_reward=str(levels["risk_reward"]),
                        confidence=features.pre_confidence,
                    )
                    if not sop.ok:
                        dropped += 1
                        reason = (sop.reason or "sop_reject").split(":")[0]
                        reject_reasons[reason] = reject_reasons.get(reason, 0) + 1
                        continue

                filled, entry_idx, entry_price = self._entry_filled(
                    candle_list,
                    idx,
                    side=features.side,
                    entry_low=float(levels["entry_low"]),
                    entry_high=float(levels["entry_high"]),
                )
                if not filled:
                    entry_unfilled += 1
                    reject_reasons["entry_unfilled"] = reject_reasons.get("entry_unfilled", 0) + 1
                    continue

                generated += 1
                trade_horizon = infer_trade_horizon(candle_list.timeframe)
                generated_at = _bar_datetime_utc(signal_bar.timestamp).astimezone(IST)
                valid_until = compute_valid_until(
                    trade_horizon, generated_at=generated_at, timeframe=candle_list.timeframe
                )
                valid_until_ms = int(valid_until.timestamp() * 1000)

                trade = self._simulate_trade(
                    candle_list,
                    entry_idx,
                    side=features.side,
                    entry=entry_price,
                    stop_loss=float(levels["stop_loss"]),
                    target=float(levels["target"]),
                    valid_until_ms=valid_until_ms,
                )
                trade.symbol = candle_list.symbol
                trade.timeframe = candle_list.timeframe
                trade.confidence = features.pre_confidence
                trade.composite_score = _composite_score(features.pre_confidence, features.mtf_score)
                trade.confluence_hits = features.confluence_hits
                trade.generated_at_ms = signal_bar.timestamp

                if trade.outcome == "expired":
                    expired_count += 1
                completed_trades.append(trade)

                if allocation is not None:
                    allocation.record(candle_list.symbol, at=_bar_datetime_utc(signal_bar.timestamp))

        start_at = datetime.fromtimestamp(candle_list.candles[0].timestamp / 1000, tz=timezone.utc)
        end_at = datetime.fromtimestamp(candle_list.candles[-1].timestamp / 1000, tz=timezone.utc)

        result = self._compute_metrics(
            trades=completed_trades,
            generated=generated,
            dropped=dropped,
            entry_unfilled=entry_unfilled,
            expired_count=expired_count,
            reject_reasons=reject_reasons,
            candle_list=candle_list,
            start_at=start_at,
            end_at=end_at,
        )
        logger.info(
            "Backtest %s %s: signals=%s wins=%s losses=%s win_rate=%.1f%% net_r=%.2f",
            candle_list.symbol,
            candle_list.timeframe,
            result.generated_signals,
            result.wins,
            result.losses,
            result.win_rate,
            result.net_r,
        )
        return result

    def run_portfolio(
        self,
        datasets: list[tuple[CandleList, dict[str, CandleList] | None]],
        *,
        gate_config: BacktestGateConfig | None = None,
        start_idx: int | None = None,
        end_idx: int | None = None,
    ) -> BacktestResult:
        """Run backtest across multiple symbol/timeframe datasets and merge metrics."""
        all_trades: list[SimulatedTrade] = []
        total_generated = 0
        total_dropped = 0
        total_entry_unfilled = 0
        total_expired = 0
        merged_rejects: dict[str, int] = {}
        starts: list[datetime] = []
        ends: list[datetime] = []

        for candle_list, htf_series in datasets:
            result = self.run(
                candle_list,
                gate_config=gate_config,
                htf_series=htf_series,
                start_idx=start_idx,
                end_idx=end_idx,
            )
            total_generated += result.generated_signals
            total_dropped += result.dropped_windows
            total_entry_unfilled += result.entry_unfilled
            total_expired += result.expired_count
            starts.append(result.start_at)
            ends.append(result.end_at)
            for reason, count in result.reject_reasons.items():
                merged_rejects[reason] = merged_rejects.get(reason, 0) + count
            for log in result.trades:
                all_trades.append(
                    SimulatedTrade(
                        side=log["side"],
                        entry=0.0,
                        stop_loss=0.0,
                        target=0.0,
                        outcome=log["outcome"],
                        r_multiple=log["r_multiple"],
                        symbol=log["symbol"],
                        timeframe=log["timeframe"],
                        confidence=log["confidence"],
                        composite_score=log["composite_score"],
                        confluence_hits=tuple(log.get("confluence_hits", [])),
                        generated_at_ms=log.get("generated_at_ms", 0),
                    )
                )

        start_at = min(starts) if starts else datetime.now(timezone.utc)
        end_at = max(ends) if ends else datetime.now(timezone.utc)
        return self._compute_metrics(
            trades=all_trades,
            generated=total_generated,
            dropped=total_dropped,
            entry_unfilled=total_entry_unfilled,
            expired_count=total_expired,
            reject_reasons=merged_rejects,
            candle_list=datasets[0][0] if datasets else CandleList("BTC", "1h", []),
            start_at=start_at,
            end_at=end_at,
        )
