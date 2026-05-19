"""LLM context helpers (MongoDB mode — no SQL historical trades)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ContextManager:
    """Placeholder for future MongoDB-backed trade history context."""

    @staticmethod
    def get_historical_context(symbol: str, limit: int = 5) -> str:
        return "Historical trade context unavailable in advisor-only mode."

    @staticmethod
    def get_market_regime_context() -> str:
        return "Market regime context is computed per symbol by the confluence engine."
