from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

from config.settings import settings
from src.database.db import get_db
from src.planitt.mongo_collections import crypto_signals_collection
from src.planitt.indicator_votes import INDICATOR_WEIGHTS, get_active_weights
from src.analysis.backtest_config import load_backtest_trade_log

logger = logging.getLogger(__name__)

LEARNED_WEIGHTS_PATH = Path("config/learned_weights.json")


class WeightOptimizer:
    def __init__(self):
        self.base_weights = INDICATOR_WEIGHTS.copy()

    async def fetch_historical_trades(self, days: int = 30) -> List[Dict[str, Any]]:
        db = await get_db()
        coll = db[crypto_signals_collection()]
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        cursor = coll.find({
            "source_backend": "coindcx_advisor",
            "status": {"$in": ["TP_HIT", "SL_HIT"]},
            "closed_at": {"$gte": cutoff.isoformat()}
        })

        trades = []
        async for doc in cursor:
            trades.append(doc)
        return trades

    def trades_from_backtest_log(self, path: Path | None = None) -> List[Dict[str, Any]]:
        """Convert backtest trade log entries to trade-like dicts for weight tuning."""
        if path is not None and path.exists():
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        else:
            raw = load_backtest_trade_log()
        trades: list[dict[str, Any]] = []
        for entry in raw:
            outcome = entry.get("outcome", "")
            status = "TP_HIT" if outcome == "tp_hit" else "SL_HIT" if outcome == "sl_hit" else None
            if status is None:
                continue
            trades.append({
                "status": status,
                "confluence_hits": entry.get("confluence_hits", []),
                "source": "backtest",
            })
        return trades

    def evaluate_performance(self, trades: List[Dict[str, Any]]) -> Dict[str, dict]:
        indicator_stats = {k: {"wins": 0, "losses": 0} for k in self.base_weights.keys()}

        for trade in trades:
            outcome = trade.get("status")
            hits = trade.get("confluence_hits", [])

            for hit in hits:
                if hit.startswith("vote_"):
                    ind_name = hit.replace("vote_", "")
                    if ind_name in indicator_stats:
                        if outcome == "TP_HIT":
                            indicator_stats[ind_name]["wins"] += 1
                        else:
                            indicator_stats[ind_name]["losses"] += 1

        return indicator_stats

    def optimize_weights(
        self,
        stats: Dict[str, dict],
        learning_rate: float = 0.05,
        *,
        target_win_rate: float = 0.65,
    ) -> Dict[str, float]:
        new_weights = get_active_weights().copy()

        for ind, stat in stats.items():
            total = stat["wins"] + stat["losses"]
            if total < 5:
                continue

            win_rate = stat["wins"] / total
            diff = win_rate - target_win_rate
            adjustment = diff * learning_rate
            new_weights[ind] = max(0.01, min(0.35, new_weights[ind] + adjustment))

        total_weight = sum(new_weights.values())
        if total_weight > 0:
            for k in new_weights:
                new_weights[k] = round(new_weights[k] / total_weight, 3)

        if "smc" in new_weights:
            new_weights["smc"] = max(0.15, new_weights["smc"])

        return new_weights

    def optimize_weights_oos(
        self,
        trades: List[Dict[str, Any]],
        *,
        train_ratio: float = 0.70,
        learning_rate: float = 0.05,
    ) -> tuple[Dict[str, float], dict]:
        """
        Train weights on first portion of trades; report OOS win-rate proxy per indicator.
        """
        if len(trades) < 10:
            weights = self.optimize_weights(self.evaluate_performance(trades), learning_rate)
            return weights, {"note": "insufficient_trades_for_oos", "trades": len(trades)}

        split = int(len(trades) * train_ratio)
        train = trades[:split]
        test = trades[split:]

        train_stats = self.evaluate_performance(train)
        new_weights = self.optimize_weights(train_stats, learning_rate)

        test_stats = self.evaluate_performance(test)
        oos_report = {
            "train_trades": len(train),
            "test_trades": len(test),
            "indicators_evaluated": sum(
                1 for s in test_stats.values() if s["wins"] + s["losses"] >= 3
            ),
        }
        return new_weights, oos_report

    async def run_optimization(
        self,
        days: int = 30,
        *,
        include_backtest_log: bool = True,
        backtest_log_path: Optional[Path] = None,
    ) -> None:
        trades = await self.fetch_historical_trades(days)
        if include_backtest_log:
            bt_trades = self.trades_from_backtest_log(backtest_log_path)
            trades = trades + bt_trades
            logger.info("Merged %d backtest trades into optimization set", len(bt_trades))

        if not trades:
            logger.info("No historical closed trades found for optimization.")
            return

        new_weights, oos_report = self.optimize_weights_oos(trades)
        LEARNED_WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LEARNED_WEIGHTS_PATH, "w", encoding="utf-8") as f:
            json.dump(new_weights, f, indent=4)

        logger.info(
            "Optimization complete. Analyzed %d trades. OOS: %s. Saved to %s",
            len(trades),
            oos_report,
            LEARNED_WEIGHTS_PATH,
        )
