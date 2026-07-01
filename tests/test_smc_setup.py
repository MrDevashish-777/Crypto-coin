"""Tests for FVG + Order Block setup detection."""

from src.planitt.smc_setup import detect_fvg_ob_setup, opposing_liquidity_tp


def _trending_bull_ohlc(n: int = 120):
    opens, highs, lows, closes, volumes = [], [], [], [], []
    price = 100.0
    for i in range(n):
        o = price
        c = price + 0.5
        h = c + 0.3
        l = o - 0.2
        opens.append(o)
        highs.append(h)
        lows.append(l)
        closes.append(c)
        volumes.append(1000.0 + i)
        price = c
    return opens, highs, lows, closes, volumes


def test_opposing_liquidity_tp_buy():
    smc_data = {
        "order_blocks": [{"type": "bearish", "bottom": 110.0, "top": 112.0, "active": True}],
        "fvgs": [],
    }
    tp = opposing_liquidity_tp(
        smc_data, entry=100.0, side="BUY", min_rr=1.5, sl=98.0,
    )
    assert tp == 110.0


def test_detect_fvg_ob_returns_none_without_zone():
    opens, highs, lows, closes, volumes = _trending_bull_ohlc()
    result = detect_fvg_ob_setup(
        opens, highs, lows, closes, volumes,
        price=closes[-1] + 50.0,
        atr=1.0,
        side="BUY",
    )
    assert result is None
