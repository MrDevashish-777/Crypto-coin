"""Tests for NWE envelope-based TP/SL in advisor targets."""

from __future__ import annotations

from src.advisor.targets import _nwe_tp_sl, compute_advisor_levels
from src.data.models import Candle, CandleList
from src.planitt.confluence import ConfluenceFeatures


def _candles_pullback_near_lower(n: int = 280) -> CandleList:
    """Uptrend then dip toward lower envelope — valid long NWE TP/SL geometry."""
    items = []
    base = 100.0
    for i in range(n - 12):
        close = base + i * 0.12
        items.append(
            Candle(
                timestamp=1_700_000_000_000 + i * 900_000,
                open=close - 0.1,
                high=close + 0.35,
                low=close - 0.35,
                close=close,
                volume=1000.0,
            )
        )
    peak = items[-1].close
    # Pull back from peak
    dip_closes = [peak - 2.5, peak - 3.0, peak - 3.5, peak - 2.8, peak - 2.0, peak - 1.2]
    for j, c in enumerate(dip_closes):
        items.append(
            Candle(
                timestamp=1_700_000_000_000 + (n - 12 + j) * 900_000,
                open=c - 0.1,
                high=c + 0.3,
                low=c - 0.5,
                close=c,
                volume=1200.0,
            )
        )
    return CandleList(symbol="BTC", timeframe="1h", candles=items)


def _features(
    cl: CandleList,
    side: str = "BUY",
    confidence: float = 0.86,
) -> ConfluenceFeatures:
    price = cl.closes[-1]
    return ConfluenceFeatures(
        asset="BTC",
        timeframe="1h",
        side=side,  # type: ignore[arg-type]
        setup_type="trend_pullback",
        price=price,
        atr=1.5,
        ema20=price + 0.5,
        ema50=price - 2.0,
        ema200=price - 8.0,
        rsi=55.0,
        macd_hist=0.5,
        macd_hist_prev=0.3,
        volume=1000.0,
        volume_ratio=1.2,
        key_level=price - 2.0,
        breakout_level=None,
        confluence_hits=(
            "ema_alignment",
            "swing_structure",
            "rsi_macd_confirmation",
            "key_level_reaction_pullback",
            "volume_spike",
            "nwe_lower_bounce",
            "vote_nwe",
        ),
        pre_confidence=confidence,
        adx=28.0,
        candlestick_pattern=None,
        candlestick_bias=None,
        candlestick_strength=0.0,
        candlestick_confirmed=False,
        agreeing_sources=6,
        mtf_score=1.0,
    )


def test_nwe_tp_sl_geometry_for_buy():
    cl = _candles_pullback_near_lower()
    price = cl.closes[-1]
    entry_mid = price
    entry_low = price * 0.995
    entry_high = price * 1.005
    levels = _nwe_tp_sl(
        side="BUY",
        entry_mid=entry_mid,
        entry_low=entry_low,
        entry_high=entry_high,
        closes=cl.closes,
        atr=1.5,
        min_rr=1.5,
    )
    assert levels is not None
    target, stop_loss = levels
    assert stop_loss < entry_low
    assert target > entry_high
    risk = entry_mid - stop_loss
    reward = target - entry_mid
    assert reward / risk >= 1.5 - 0.01


def test_compute_advisor_levels_uses_nwe_envelope():
    cl = _candles_pullback_near_lower()
    features = _features(cl)
    levels = compute_advisor_levels(features, candle_list=cl)
    assert levels.get("tp_sl_method") == "nwe_envelope"
    assert levels["stop_loss"] < levels["entry_low"]
    assert levels["target"] > levels["entry_high"]
    assert "NWE" in levels.get("chart_indicators", [])
