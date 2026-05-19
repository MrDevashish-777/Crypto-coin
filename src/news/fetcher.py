"""News ingestion service with dedupe + symbol/sentiment enrichment."""

from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional

import httpx

from src.news.sentiment import classify_sentiment, extract_symbols

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q=crypto%20market&hl=en-US&gl=US&ceid=US:en"
COINGECKO_NEWS = "https://api.coingecko.com/api/v3/news"
BINANCE_ANNOUNCEMENTS = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"
FNG_URL = "https://api.alternative.me/fng/?limit=1"


def _sanitize_text(value: str) -> str:
    text = re.sub(r"<[^>]*>", " ", value or "")
    return re.sub(r"\s+", " ", text).strip()


def _to_datetime(value: Optional[str]) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


class NewsFetcher:
    """Fetch and normalize free-tier crypto news feeds."""

    def __init__(self) -> None:
        self.timeout = httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0)

    async def fetch_all_news(self, limit_per_feed: int = 20) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            tasks = [
                self._fetch_coingecko(client, limit_per_feed),
                self._fetch_google_rss(client, limit_per_feed),
                self._fetch_binance_announcements(client, limit_per_feed),
                self._fetch_fear_greed(client),
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        merged: list[dict[str, Any]] = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("News source failed: %s", result)
                continue
            merged.extend(result)
        deduped: dict[str, dict[str, Any]] = {}
        for item in merged:
            key = f"{item.get('source')}|{item.get('headline')}"
            deduped[key] = item
        ordered = sorted(deduped.values(), key=lambda x: x["published_at"], reverse=True)
        return ordered

    async def _fetch_coingecko(self, client: httpx.AsyncClient, limit: int) -> list[dict[str, Any]]:
        response = await client.get(COINGECKO_NEWS, params={"category": "general", "per_page": limit})
        response.raise_for_status()
        raw = response.json()
        items = raw.get("data", raw) if isinstance(raw, dict) else raw
        normalized: list[dict[str, Any]] = []
        for item in items[:limit]:
            headline = _sanitize_text(str(item.get("title") or ""))
            summary = _sanitize_text(str(item.get("description") or ""))
            published = int(item.get("updated_at") or item.get("created_at") or 0)
            published_at = datetime.fromtimestamp(published, tz=timezone.utc) if published > 0 else datetime.now(timezone.utc)
            sentiment, score = classify_sentiment(headline, summary)
            normalized.append(
                {
                    "headline": headline,
                    "summary": summary[:280],
                    "url": str(item.get("url") or ""),
                    "source": "coingecko",
                    "published_at": published_at,
                    "symbols": extract_symbols(f"{headline} {summary}"),
                    "sentiment": sentiment,
                    "sentiment_score": score,
                    "relevance_score": 0.8,
                    "sentiment_model": "rule_v2",
                }
            )
        return normalized

    async def _fetch_google_rss(self, client: httpx.AsyncClient, limit: int) -> list[dict[str, Any]]:
        response = await client.get(GOOGLE_NEWS_RSS)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        items = root.findall(".//item")
        normalized: list[dict[str, Any]] = []
        for item in items[:limit]:
            headline = _sanitize_text(item.findtext("title", ""))
            summary = _sanitize_text(item.findtext("description", ""))
            sentiment, score = classify_sentiment(headline, summary)
            normalized.append(
                {
                    "headline": headline,
                    "summary": summary[:280],
                    "url": _sanitize_text(item.findtext("link", "")),
                    "source": "google_news_rss",
                    "published_at": _to_datetime(item.findtext("pubDate", "")),
                    "symbols": extract_symbols(f"{headline} {summary}"),
                    "sentiment": sentiment,
                    "sentiment_score": score,
                    "relevance_score": 0.65,
                    "sentiment_model": "rule_v2",
                }
            )
        return normalized

    async def _fetch_binance_announcements(self, client: httpx.AsyncClient, limit: int) -> list[dict[str, Any]]:
        payload = {
            "type": 1,
            "catalogId": 48,
            "pageNo": 1,
            "pageSize": max(5, min(limit, 30)),
        }
        response = await client.post(BINANCE_ANNOUNCEMENTS, json=payload)
        response.raise_for_status()
        data = response.json().get("data", {})
        articles = data.get("articles", [])
        normalized: list[dict[str, Any]] = []
        for item in articles:
            headline = _sanitize_text(str(item.get("title") or ""))
            summary = _sanitize_text(str(item.get("summary") or ""))
            release_ts = int(item.get("releaseDate", 0))
            published_at = datetime.fromtimestamp(release_ts / 1000, tz=timezone.utc) if release_ts > 0 else datetime.now(timezone.utc)
            sentiment, score = classify_sentiment(headline, summary)
            normalized.append(
                {
                    "headline": headline,
                    "summary": summary[:280],
                    "url": f"https://www.binance.com/en/support/announcement/{item.get('code', '')}",
                    "source": "binance_announcements",
                    "published_at": published_at,
                    "symbols": extract_symbols(f"{headline} {summary}"),
                    "sentiment": sentiment,
                    "sentiment_score": score,
                    "relevance_score": 0.9,
                    "sentiment_model": "rule_v2",
                }
            )
        return normalized

    async def _fetch_fear_greed(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        response = await client.get(FNG_URL)
        response.raise_for_status()
        payload = response.json().get("data", [])
        if not payload:
            return []
        row = payload[0]
        value = int(row.get("value", 50))
        sentiment = "bullish" if value >= 60 else "bearish" if value <= 40 else "neutral"
        score = abs(value - 50) / 50
        published_at = datetime.fromtimestamp(int(row.get("timestamp", 0)), tz=timezone.utc)
        return [
            {
                "headline": f"Crypto Fear & Greed Index at {value}",
                "summary": f"Market sentiment index currently at {value} ({row.get('value_classification', 'Neutral')}).",
                "url": "https://alternative.me/crypto/fear-and-greed-index/",
                "source": "fear_greed_index",
                "published_at": published_at,
                "symbols": [],
                "sentiment": sentiment,
                "sentiment_score": max(0.5, score),
                "relevance_score": 0.7,
                "sentiment_model": "index_v1",
            }
        ]
