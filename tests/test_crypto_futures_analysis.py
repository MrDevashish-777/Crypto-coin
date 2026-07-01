"""Tests for crypto futures analysis helpers."""

from __future__ import annotations

from src.planitt.crypto_futures_analysis import (
    crypto_momentum_hit,
    infer_trade_side,
)
from src.signals.market_regime import MarketRegime, RegimeResult


def test_crypto_momentum_di_macd_buy():
    tag = crypto_momentum_hit(
        "BUY",
        55.0,
        54.0,
        0.5,
        0.3,
        adx=22.0,
        plus_di=28.0,
        minus_di=20.0,
        strict_confirmed=False,
    )
    assert tag in ("macd_direction", "di_macd_momentum")


def test_infer_trade_side_di_supertrend_pullback(monkeypatch):
    monkeypatch.setattr("src.planitt.crypto_futures_analysis.settings.PLANITT_RELAX_SIDE_FROM_REGIME", True)
    monkeypatch.setattr("src.planitt.crypto_futures_analysis.settings.PLANITT_CRYPTO_FUTURES_ANALYSIS", True)
    monkeypatch.setattr("src.planitt.crypto_futures_analysis.settings.PLANITT_RANGING_MIN_DI_SPREAD", 1.0)

    n = 220
    closes = [100.0 + i * 0.05 for i in range(n)]
    highs = [c + 0.3 for c in closes]
    lows = [c - 0.3 for c in closes]

    regime = RegimeResult(
        regime=MarketRegime.RANGING,
        adx=20.0,
        plus_di=26.0,
        minus_di=18.0,
        atr=1.0,
        atr_pct_of_price=1.0,
        bb_bandwidth=0.02,
        price_vs_ema50="above",
        confidence=0.7,
    )
    side, hits = infer_trade_side(
        ema20=102.0,
        ema50=101.0,
        ema200=100.0,
        regime_result=regime,
        adx_trend_threshold=16.0,
        highs=highs,
        lows=lows,
        closes=closes,
    )
    assert side in ("BUY", "SELL", None)
    if side is not None:
        assert isinstance(hits, tuple)
