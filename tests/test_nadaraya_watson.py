"""Tests for Nadaraya-Watson Envelope (non-repainting)."""

from src.indicators.nadaraya_watson import NadarayaWatsonEnvelope


def _trending_closes(n: int = 300, step: float = 0.5) -> list[float]:
    base = 100.0
    return [base + i * step for i in range(n)]


def test_nwe_produces_bands():
    closes = _trending_closes()
    nwe = NadarayaWatsonEnvelope(bandwidth=8.0, multiplier=3.0, lookback=200)
    bands = nwe.calculate(closes)
    assert len(bands["midpoint"]) == len(closes)
    assert bands["upper"][-1] > bands["midpoint"][-1] > bands["lower"][-1]


def test_bull_bounce_detected():
    closes = [100.0] * 50
    # Dip below lower band then recover
    for i in range(30):
        closes.append(100.0 - (i + 1) * 0.8)
    closes.extend([92.0, 93.5, 95.0, 97.0, 99.0, 101.0])

    nwe = NadarayaWatsonEnvelope(bandwidth=6.0, multiplier=2.5, lookback=120)
    snap = nwe.snapshot(closes)
    assert snap is not None
    assert snap.upper > snap.midpoint > snap.lower


def test_nwe_vote_strength_for_buy():
    closes = _trending_closes(250)
    nwe = NadarayaWatsonEnvelope(bandwidth=8.0, multiplier=3.0, lookback=200)
    snap = nwe.snapshot(closes)
    assert snap is not None
    strength = nwe.signal_strength(snap, "BUY")
    assert 0.0 <= strength <= 1.0
