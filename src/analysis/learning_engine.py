import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any

from config.settings import settings
from src.database.db import get_db
from src.planitt.mongo_collections import crypto_signals_collection
from src.planitt.indicator_votes import INDICATOR_WEIGHTS, get_active_weights

logger = logging.getLogger(__name__)

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

    def optimize_weights(self, stats: Dict[str, dict], learning_rate: float = 0.05) -> Dict[str, float]:
        new_weights = get_active_weights().copy()
        
        for ind, stat in stats.items():
            total = stat["wins"] + stat["losses"]
            if total < 5:
                continue # Not enough data
                
            win_rate = stat["wins"] / total
            
            # Target win rate from SOP is 65%
            # If an indicator provides > 65% WR, boost its weight. If < 65%, penalize.
            diff = win_rate - 0.65
            
            # Update weight with simple gradient descent
            adjustment = diff * learning_rate
            
            new_weights[ind] = max(0.01, min(0.35, new_weights[ind] + adjustment))
            
        # Normalize weights so they sum to ~1.0
        total_weight = sum(new_weights.values())
        if total_weight > 0:
            for k in new_weights:
                new_weights[k] = round(new_weights[k] / total_weight, 3)
                
        # Ensure SMC (Liquidity) remains high as per user instruction
        if "smc" in new_weights:
            new_weights["smc"] = max(0.15, new_weights["smc"])
            
        return new_weights

    async def run_optimization(self, days: int = 30) -> None:
        trades = await self.fetch_historical_trades(days)
        if not trades:
            logger.info("No historical closed trades found for optimization.")
            return
            
        stats = self.evaluate_performance(trades)
        new_weights = self.optimize_weights(stats)
        
        with open("config/learned_weights.json", "w") as f:
            json.dump(new_weights, f, indent=4)
            
        logger.info(f"Optimization complete. Analyzed {len(trades)} trades. Saved to learned_weights.json")
