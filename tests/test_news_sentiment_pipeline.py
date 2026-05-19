from __future__ import annotations

from src.news.sentiment import classify_sentiment, extract_symbols


def test_news_sentiment_bullish_classification() -> None:
    sentiment, score = classify_sentiment("BTC breakout after strong demand from ETFs")
    assert sentiment == "bullish"
    assert score >= 0.55


def test_news_symbol_extraction() -> None:
    symbols = extract_symbols("ETH and BTC gain momentum while SOL sees inflows")
    assert "BTC" in symbols
    assert "ETH" in symbols
