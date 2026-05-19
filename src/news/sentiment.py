from __future__ import annotations

import re
from typing import Literal

from config.constants import CRYPTO_PAIRS

SentimentLabel = Literal["bullish", "bearish", "neutral"]

_BULLISH_TERMS = {
    "breakout",
    "surge",
    "rally",
    "adoption",
    "approval",
    "accumulate",
    "bullish",
    "strong demand",
    "record high",
    "listing",
}
_BEARISH_TERMS = {
    "hack",
    "exploit",
    "selloff",
    "liquidation",
    "ban",
    "lawsuit",
    "delist",
    "bearish",
    "record low",
    "warning",
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def extract_symbols(text: str) -> list[str]:
    normalized = normalize_text(text)
    found: list[str] = []
    for symbol in CRYPTO_PAIRS:
        token = symbol.lower()
        if re.search(rf"\b{re.escape(token)}\b", normalized):
            found.append(symbol)
    return found


def classify_sentiment(headline: str, summary: str = "") -> tuple[SentimentLabel, float]:
    text = normalize_text(f"{headline} {summary}")
    bull_hits = sum(1 for term in _BULLISH_TERMS if term in text)
    bear_hits = sum(1 for term in _BEARISH_TERMS if term in text)
    total_hits = bull_hits + bear_hits
    if total_hits == 0:
        return "neutral", 0.5
    if bull_hits > bear_hits:
        score = min(1.0, 0.55 + ((bull_hits - bear_hits) * 0.1))
        return "bullish", score
    if bear_hits > bull_hits:
        score = min(1.0, 0.55 + ((bear_hits - bull_hits) * 0.1))
        return "bearish", score
    return "neutral", 0.5
