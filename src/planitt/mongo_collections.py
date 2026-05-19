"""Resolve Mongo collection names for split vs unified Planitt storage."""

from __future__ import annotations

from typing import Any

from config.settings import settings


def crypto_signals_collection() -> str:
    """Return collection name for crypto signal upserts and reads."""
    if settings.UNIFIED_COLLECTIONS_ENABLED:
        return "signals"
    return "signals_crypto"


def crypto_news_collection() -> str:
    """Return collection name for crypto news upserts and reads."""
    if settings.UNIFIED_COLLECTIONS_ENABLED:
        return "news"
    return "news_crypto"


def crypto_signal_find_filter(base: dict[str, Any]) -> dict[str, Any]:
    """Merge asset_class=CRYPTO when using unified `signals` collection."""
    merged = dict(base)
    if settings.UNIFIED_COLLECTIONS_ENABLED:
        merged["asset_class"] = "CRYPTO"
    return merged
