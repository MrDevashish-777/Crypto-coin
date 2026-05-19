from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from config.settings import settings
from src.database.db import get_db
from src.planitt.mongo_collections import (
    crypto_news_collection,
    crypto_signal_find_filter,
    crypto_signals_collection,
)

logger = logging.getLogger(__name__)

SignalStatus = Literal["OPEN", "TP_HIT", "SL_HIT", "EXPIRED", "CANCELLED"]
SignalOutcome = Literal["tp_hit", "sl_hit", "expired", "cancelled", "open"]

AUTO_PUBLISH_CONFIDENCE = 0.80
SIGNAL_SCHEMA_VERSION = "2.0.0"
NEWS_SCHEMA_VERSION = "2.0.0"


class SignalDocument(BaseModel):
    """Canonical MongoDB signal document for Crypto Bot."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        protected_namespaces=(),
    )

    idempotency_key: str
    symbol: str
    asset: str
    asset_class: Literal["CRYPTO"] = "CRYPTO"
    source_backend: str = "crypto_bot"
    timeframe: str
    signal_type: Literal["BUY", "SELL", "HOLD"]
    strategy: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    entry_price: float = Field(..., gt=0)
    target_price: float = Field(..., gt=0)
    stop_loss: float = Field(..., gt=0)
    risk_reward_ratio: float = Field(..., ge=0)
    technical_summary: str
    timestamp: datetime
    expires_at: Optional[datetime] = None
    status: SignalStatus = "OPEN"
    outcome: SignalOutcome = "open"
    closure_reason: Optional[str] = None
    closed_at: Optional[datetime] = None
    pnl_r_multiple: Optional[float] = None
    is_published: bool = False
    research_status: str = "pending"
    schema_version: str = SIGNAL_SCHEMA_VERSION
    model_version: str = "planitt_v2"
    ai_verification: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class NewsDocument(BaseModel):
    """Canonical MongoDB news document for Crypto Bot."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        protected_namespaces=(),
    )

    dedupe_key: str
    headline: str
    summary: str
    url: str
    source: str
    symbols: list[str] = []
    sentiment: Literal["bullish", "bearish", "neutral"]
    sentiment_score: float = Field(..., ge=0.0, le=1.0)
    sentiment_model: str
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    asset_class: Literal["CRYPTO"] = "CRYPTO"
    published_at: datetime
    fetched_at: datetime
    expires_at: datetime
    is_published: bool = True
    source_backend: str = "crypto_bot"
    schema_version: str = NEWS_SCHEMA_VERSION


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc_datetime(value: Any) -> datetime | None:
    """Normalize datetime/string values to timezone-aware UTC."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _parse_rr_ratio(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if ":" in text:
        parts = text.split(":", 1)
        try:
            return float(parts[1].strip())
        except ValueError:
            return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def build_signal_document(
    *,
    payload: dict[str, Any],
    symbol: str,
    timeframe: str,
    dedup_key: str,
    status: SignalStatus = "OPEN",
    verification: Optional[dict[str, Any]] = None,
) -> SignalDocument:
    """Build canonical signal doc from processor payload."""

    ts = _utc_now()
    created_at = _as_utc_datetime(payload.get("created_at"))
    if created_at is not None:
        ts = created_at

    expires_at = _as_utc_datetime(payload.get("expires_at"))

    entry_range = payload.get("entry_range") or [0.0, 0.0]
    tp = payload.get("take_profit") or {}
    confidence = float(payload.get("confidence", 0.0))
    if confidence > 1.0:
        confidence = confidence / 100.0
    confidence = max(0.0, min(1.0, confidence))

    adjusted_conf = confidence
    verdict = "APPROVE"
    is_published = confidence >= AUTO_PUBLISH_CONFIDENCE
    if verification:
        adjusted_conf = float(verification.get("adjusted_confidence", confidence))
        verdict = str(verification.get("verdict", "APPROVE")).upper()
        is_published = verdict != "REJECT" and adjusted_conf >= AUTO_PUBLISH_CONFIDENCE

    return SignalDocument(
        idempotency_key=dedup_key,
        symbol=symbol,
        asset=str(payload.get("asset") or symbol),
        timeframe=timeframe,
        signal_type=str(payload.get("signal_type") or "HOLD"),
        strategy=str(payload.get("strategy") or "planitt"),
        confidence_score=adjusted_conf,
        entry_price=float(entry_range[0] or 0.0),
        target_price=float(tp.get("tp1") or 0.0),
        stop_loss=float(payload.get("stop_loss") or 0.0),
        risk_reward_ratio=_parse_rr_ratio(payload.get("risk_reward_ratio")),
        technical_summary=str(payload.get("reason") or ""),
        timestamp=ts,
        expires_at=expires_at,
        status=status,
        outcome="open",
        is_published=is_published,
        ai_verification=verification,
        created_at=ts,
        updated_at=_utc_now(),
    )


async def persist_signal_document(document: SignalDocument) -> None:
    """Upsert a signal document in canonical collection."""

    db = await get_db()
    coll = db[crypto_signals_collection()]
    set_doc = document.model_dump()
    set_doc.pop("created_at", None)
    await coll.update_one(
        {"idempotency_key": document.idempotency_key},
        {"$set": set_doc, "$setOnInsert": {"created_at": document.created_at}},
        upsert=True,
    )


async def close_completed_signals(symbol: str, timeframe: str, latest_price: float) -> int:
    """Close completed open signals once TP/SL/expiry conditions are met."""

    db = await get_db()
    coll = db[crypto_signals_collection()]
    now = _utc_now()
    query = crypto_signal_find_filter({"symbol": symbol, "timeframe": timeframe, "status": "OPEN"})
    active_docs = await coll.find(query, {"_id": 0}).to_list(200)
    closed_count = 0
    for doc in active_docs:
        signal_type = str(doc.get("signal_type", "HOLD"))
        entry = float(doc.get("entry_price") or 0.0)
        tp = float(doc.get("target_price") or 0.0)
        sl = float(doc.get("stop_loss") or 0.0)
        expires_at = _as_utc_datetime(doc.get("expires_at"))
        status: SignalStatus = "OPEN"
        outcome: SignalOutcome = "open"
        closure_reason: Optional[str] = None
        pnl_r_multiple: Optional[float] = None

        if expires_at is not None and expires_at <= now:
            status = "EXPIRED"
            outcome = "expired"
            closure_reason = "validity_elapsed"
        elif signal_type == "BUY":
            if latest_price >= tp:
                status = "TP_HIT"
                outcome = "tp_hit"
            elif latest_price <= sl:
                status = "SL_HIT"
                outcome = "sl_hit"
        elif signal_type == "SELL":
            if latest_price <= tp:
                status = "TP_HIT"
                outcome = "tp_hit"
            elif latest_price >= sl:
                status = "SL_HIT"
                outcome = "sl_hit"

        if status != "OPEN":
            risk = abs(entry - sl)
            reward = abs(latest_price - entry)
            pnl_r_multiple = (reward / risk) if risk > 0 else None
            await coll.update_one(
                {"idempotency_key": doc["idempotency_key"]},
                {
                    "$set": {
                        "status": status,
                        "outcome": outcome,
                        "closed_at": now,
                        "closure_reason": closure_reason or outcome,
                        "pnl_r_multiple": pnl_r_multiple,
                        "updated_at": now,
                    }
                },
            )
            closed_count += 1
    return closed_count


def build_news_document(
    *,
    headline: str,
    summary: str,
    url: str,
    source: str,
    symbols: list[str],
    sentiment: Literal["bullish", "bearish", "neutral"],
    sentiment_score: float,
    relevance_score: float,
    sentiment_model: str,
    published_at: datetime,
) -> NewsDocument:
    """Build canonical crypto news document."""

    dedupe_raw = f"{source}|{headline}|{published_at.isoformat()}"
    dedupe_key = hashlib.sha256(dedupe_raw.encode("utf-8")).hexdigest()
    now = _utc_now()
    return NewsDocument(
        dedupe_key=dedupe_key,
        headline=headline,
        summary=summary,
        url=url,
        source=source,
        symbols=symbols,
        sentiment=sentiment,
        sentiment_score=sentiment_score,
        sentiment_model=sentiment_model,
        relevance_score=relevance_score,
        published_at=published_at,
        fetched_at=now,
        expires_at=now + timedelta(hours=24),
    )


async def persist_news_documents(documents: list[NewsDocument]) -> int:
    """Upsert canonical news docs and return write count."""

    if not documents:
        return 0
    db = await get_db()
    coll = db[crypto_news_collection()]
    writes = 0
    for document in documents:
        await coll.update_one(
            {"dedupe_key": document.dedupe_key},
            {"$set": document.model_dump()},
            upsert=True,
        )
        writes += 1
    return writes


async def get_symbol_news_sentiment(symbol: str, hours: int = 24) -> float:
    """Return weighted sentiment in range [-1, 1] for a symbol."""

    db = await get_db()
    coll = db[crypto_news_collection()]
    cutoff = _utc_now() - timedelta(hours=hours)
    news_q: dict = {"symbols": symbol, "published_at": {"$gte": cutoff}}
    if settings.UNIFIED_COLLECTIONS_ENABLED:
        news_q["asset_class"] = "CRYPTO"
    docs = await coll.find(
        news_q,
        {"_id": 0, "sentiment": 1, "sentiment_score": 1, "relevance_score": 1},
    ).to_list(200)
    if not docs:
        return 0.0
    weighted_sum = 0.0
    weight_total = 0.0
    for doc in docs:
        sentiment = str(doc.get("sentiment", "neutral"))
        direction = 1.0 if sentiment == "bullish" else -1.0 if sentiment == "bearish" else 0.0
        score = float(doc.get("sentiment_score") or 0.0)
        relevance = float(doc.get("relevance_score") or 0.0)
        weight = max(0.05, relevance)
        weighted_sum += direction * score * weight
        weight_total += weight
    if weight_total <= 0:
        return 0.0
    return max(-1.0, min(1.0, weighted_sum / weight_total))
