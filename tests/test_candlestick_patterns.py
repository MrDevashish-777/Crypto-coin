from src.indicators.candlestick_patterns import detect_latest_candlestick_pattern


def test_detects_bullish_engulfing():
    pattern = detect_latest_candlestick_pattern(
        opens=[100, 101, 98],
        highs=[102, 102, 104],
        lows=[99, 97, 97],
        closes=[101, 98, 103],
        volumes=[1000, 950, 1500],
    )
    assert pattern is not None
    assert pattern["pattern_name"] == "bullish_engulfing"
    assert pattern["bias"] == "bull"


def test_returns_none_when_no_pattern():
    pattern = detect_latest_candlestick_pattern(
        opens=[100, 100.5, 101.0, 101.3],
        highs=[101.0, 101.2, 101.5, 101.7],
        lows=[99.8, 100.2, 100.8, 101.1],
        closes=[100.4, 100.9, 101.2, 101.4],
        volumes=[1000, 980, 990, 1005],
    )
    assert pattern is None
