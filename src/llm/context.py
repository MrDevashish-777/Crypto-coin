"""
LLM Context Manager
Provides historical context and performance data to LLMs for 'learning'
"""

import logging
from typing import List, Dict, Any
import json
import time

# #region agent log
_debug_log_path = "/Users/parthshende/Downloads/Planitt-Inhouse-App/.cursor/debug-50440f.log"


def _debug_log(hypothesis_id: str, message: str, data: Dict[str, Any]) -> None:
    payload = {
        "sessionId": "50440f",
        "runId": "post-fix-2",
        "hypothesisId": hypothesis_id,
        "location": "Crypto Bot/src/llm/context.py",
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(_debug_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception:
        pass


try:
    from src.database.db import SessionLocal
    from src.database.models import TradeExecution, PerformanceMetric
    DB_CONTEXT_AVAILABLE = True
    _debug_log("H10", "sqlalchemy_context_import_ok", {"db_context_available": True})
except Exception as db_import_error:
    SessionLocal = None
    TradeExecution = None
    PerformanceMetric = None
    DB_CONTEXT_AVAILABLE = False
    _debug_log("H10", "sqlalchemy_context_import_failed", {"error": str(db_import_error)})
# #endregion

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages LLM context from historical data"""

    @staticmethod
    def get_historical_context(symbol: str, limit: int = 5) -> str:
        """
        Get historical context of successful trades for a symbol
        """
        # #region agent log
        _debug_log(
            "H10",
            "get_historical_context_called",
            {"symbol": symbol, "limit": limit, "db_context_available": DB_CONTEXT_AVAILABLE},
        )
        # #endregion
        if not DB_CONTEXT_AVAILABLE or SessionLocal is None:
            return "Historical context unavailable in MongoDB mode."
        db = SessionLocal()
        try:
            # Fetch last successful trades
            successful_trades = (
                db.query(TradeExecution)
                .filter(TradeExecution.symbol == symbol, TradeExecution.pnl > 0)
                .order_by(TradeExecution.exit_at.desc())
                .limit(limit)
                .all()
            )
            
            if not successful_trades:
                return "No historical successful trades for this symbol yet."
            
            context = "Historical Successful Trades for context:\n"
            for trade in successful_trades:
                context += (
                    f"- Type: {trade.position_type}, Entry: {trade.entry_price}, "
                    f"Exit: {trade.exit_price}, PnL: {trade.pnl_percent:.2f}%\n"
                )
            
            # Add general performance
            perf = db.query(PerformanceMetric).filter(PerformanceMetric.symbol == symbol).first()
            if perf:
                context += f"\nOverall Symbol Performance: Win Rate {perf.win_rate:.1%}, Total PnL: {perf.total_pnl:.2f}\n"
                
            return context
        except Exception as e:
            logger.error(f"Error fetching historical context: {str(e)}")
            return "Error fetching historical context."
        finally:
            db.close()

    @staticmethod
    def get_market_regime_context() -> str:
        """
        Get general market regime context
        """
        # In a real app, this might analyze BTC/ETH trends
        return "Market Regime: Trending bullish on high timeframes, consolidation on low timeframes."
