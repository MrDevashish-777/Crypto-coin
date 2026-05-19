"""
Crypto Bot news endpoint with ingestion and sentiment enrichment.
GET /api/v1/news
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from fastapi import APIRouter

from src.database.db import get_db
from config.settings import settings
from src.news.fetcher import NewsFetcher
from src.planitt.persistence import build_news_document, persist_news_documents

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/news", tags=["news"])
UNIFIED_COLLECTIONS_ENABLED = settings.UNIFIED_COLLECTIONS_ENABLED if hasattr(settings, "UNIFIED_COLLECTIONS_ENABLED") else False

CACHE_TTL_MINUTES = 30

_news_cache: dict = {"data": [], "fetched_at": None}
_fetcher = NewsFetcher()


def _time_ago(dt: datetime) -> str:
    delta = datetime.now(timezone.utc) - dt.replace(tzinfo=timezone.utc)
    s = int(delta.total_seconds())
    if s < 60:
        return "just now"
    if s < 3600:
        return f"{s // 60} min ago"
    if s < 86400:
        return f"{s // 3600} hr ago"
    return f"{s // 86400} days ago"


@router.get("")
async def get_crypto_news(limit: int = 20):
    """Get crypto news with enrichment and MongoDB fallback."""
    global _news_cache

    if _news_cache["fetched_at"]:
        age = (datetime.now(timezone.utc) - _news_cache["fetched_at"]).total_seconds()
        if age < CACHE_TTL_MINUTES * 60 and _news_cache["data"]:
            return {"news": _news_cache["data"][:limit], "source": "cache", "count": min(limit, len(_news_cache["data"]))}

    try:
        raw_items = await _fetcher.fetch_all_news(limit_per_feed=max(20, limit))
        docs = []
        response_items = []
        for idx, item in enumerate(raw_items):
            published_at = item.get("published_at", datetime.now(timezone.utc))
            document = build_news_document(
                headline=str(item.get("headline") or ""),
                summary=str(item.get("summary") or ""),
                url=str(item.get("url") or ""),
                source=str(item.get("source") or "unknown"),
                symbols=list(item.get("symbols") or []),
                sentiment=str(item.get("sentiment") or "neutral"),
                sentiment_score=float(item.get("sentiment_score") or 0.5),
                relevance_score=float(item.get("relevance_score") or 0.5),
                sentiment_model=str(item.get("sentiment_model") or "rule_v2"),
                published_at=published_at if isinstance(published_at, datetime) else datetime.now(timezone.utc),
            )
            docs.append(document)
            response_items.append(
                {
                    "id": f"news-{idx}",
                    "headline": document.headline,
                    "source": document.source,
                    "url": document.url,
                    "asset_class": "CRYPTO",
                    "sentiment": document.sentiment.title(),
                    "date": document.published_at.strftime("%d %b %Y"),
                    "timeAgo": _time_ago(document.published_at),
                    "published_at": document.published_at.isoformat(),
                    "symbols": document.symbols,
                    "sentiment_score": document.sentiment_score,
                    "relevance_score": document.relevance_score,
                }
            )
        await persist_news_documents(docs)
        _news_cache = {"data": response_items, "fetched_at": datetime.now(timezone.utc)}
        return {"news": response_items[:limit], "source": "multi_source", "count": min(limit, len(response_items))}
    except Exception as e:
        logger.warning("Live news fetch failed: %s", e)

    try:
        db = await get_db()
        collection = db.news if UNIFIED_COLLECTIONS_ENABLED else db.news_crypto
        docs = await collection.find({"asset_class": "CRYPTO"}).sort("published_at", -1).limit(limit).to_list(limit)
        for d in docs:
            d.pop("_id", None)
        return {"news": docs, "source": "mongodb_cache", "count": len(docs)}
    except Exception as e:
        logger.error("MongoDB news fallback failed: %s", e)
        return {"news": [], "source": "error", "count": 0}
