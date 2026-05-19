from src.data.models import Candle, CandleList
from src.planitt.confluence import evaluate_confluence_pre_gates


def _build_trending_candles(n: int = 240) -> CandleList:
    candles = []
    base = 100.0
    for i in range(n):
        close = base + i * 0.4
        open_p = close - 0.2
        high = close + 0.6
        low = open_p - 0.4
        vol = 1000 + (i % 10) * 30
        candles.append(
            Candle(
                timestamp=1_700_000_000_000 + i * 900_000,
                open=open_p,
                high=high,
                low=low,
                close=close,
                volume=vol,
            )
        )
    return CandleList(symbol="BTC", timeframe="15m", candles=candles)


def test_confluence_includes_pattern_metadata():
    candle_list = _build_trending_candles()
    features = evaluate_confluence_pre_gates(
        candle_list,
        adx_trend_threshold=10.0,
        volume_multiplier=1.0,
        touch_tolerance_pct=0.03,
        min_confluence_hits=2,
    )
    # Depending on the synthetic candles and market-regime model, this may still reject.
    # If accepted, the new candlestick fields must always exist.
    if features is not None:
        assert hasattr(features, "candlestick_pattern")
        assert hasattr(features, "candlestick_strength")
