import sys
import pytest

if sys.version_info < (3, 10):
    pytest.skip("Confluence strategy imports require Python 3.10+", allow_module_level=True)

from src.signals.strategies.confluence_strategy import ConfluenceStrategy


def test_confluence_strategy_pattern_vote_callable():
    strategy = ConfluenceStrategy()
    opens = [100, 101, 98]
    highs = [102, 102, 104]
    lows = [99, 97, 97]
    closes = [101, 98, 103]
    volumes = [900, 850, 1400]

    direction, score = strategy._calc_candlestick_vote(opens, highs, lows, closes, volumes)
    assert direction in ("bull", "bear", None)
    assert 0.0 <= score <= 1.0
