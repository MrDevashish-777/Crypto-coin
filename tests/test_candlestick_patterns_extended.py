"""Tests for expanded candlestick patterns."""

from src.indicators.candlestick_patterns import detect_latest_candlestick_pattern


def _ohlcv_from_bars(bars: list[tuple[float, float, float, float, float]]):
    opens, highs, lows, closes, volumes = [], [], [], [], []
    for o, h, l, c, v in bars:
        opens.append(o)
        highs.append(h)
        lows.append(l)
        closes.append(c)
        volumes.append(v)
    return opens, highs, lows, closes, volumes


def test_three_white_soldiers_detected():
    bars = [
        (98, 100, 97, 99, 1000),
        (99, 101, 98, 100.5, 1100),
        (100.5, 102, 100, 101.5, 1200),
        (101, 103, 100.5, 102.5, 1300),
        (102, 104, 101.5, 103.5, 1400),
    ]
    o, h, l, c, v = _ohlcv_from_bars(bars)
    pat = detect_latest_candlestick_pattern(opens=o, highs=h, lows=l, closes=c, volumes=v)
    assert pat is not None
    assert pat["pattern_name"] == "three_white_soldiers"
    assert pat["bias"] == "bull"


def test_inside_bar_detected():
    bars = [
        (100, 105, 98, 102, 1000),
        (102, 106, 100, 104, 1100),
        (103, 104.5, 101, 103.5, 900),
        (103.2, 104, 101.5, 103, 950),
    ]
    o, h, l, c, v = _ohlcv_from_bars(bars)
    pat = detect_latest_candlestick_pattern(opens=o, highs=h, lows=l, closes=c, volumes=v)
    assert pat is not None
    assert pat["pattern_name"] == "inside_bar"
