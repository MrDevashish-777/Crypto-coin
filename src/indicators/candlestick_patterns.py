from __future__ import annotations

from typing import Optional, Literal, TypedDict


PatternBias = Literal["bull", "bear"]


class PatternSignal(TypedDict):
    pattern_name: str
    bias: PatternBias
    strength: float
    confirmation: bool
    bar_index: int


def _body(open_p: float, close_p: float) -> float:
    return abs(close_p - open_p)


def _upper_wick(open_p: float, high: float, close_p: float) -> float:
    return high - max(open_p, close_p)


def _lower_wick(open_p: float, low: float, close_p: float) -> float:
    return min(open_p, close_p) - low


def _volume_confirmation(volumes: list[float], lookback: int = 20) -> bool:
    if len(volumes) < lookback + 1:
        return False
    baseline = sum(volumes[-(lookback + 1) : -1]) / lookback
    if baseline <= 0:
        return False
    return volumes[-1] >= baseline * 1.1


def detect_latest_candlestick_pattern(
    *,
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float],
) -> Optional[PatternSignal]:
    if min(len(opens), len(highs), len(lows), len(closes), len(volumes)) < 4:
        return None

    i = len(closes) - 1
    # Last 3 candles for 3-candle patterns
    o0, h0, l0, c0 = opens[i - 2], highs[i - 2], lows[i - 2], closes[i - 2]
    o1, h1, l1, c1 = opens[i - 1], highs[i - 1], lows[i - 1], closes[i - 1]
    o2, h2, l2, c2 = opens[i], highs[i], lows[i], closes[i]

    body0 = _body(o0, c0)
    body1 = _body(o1, c1)
    body2 = _body(o2, c2)
    range2 = max(h2 - l2, 1e-9)
    vol_ok = _volume_confirmation(volumes)

    # Bullish engulfing
    if c1 < o1 and c2 > o2 and o2 <= c1 and c2 >= o1:
        strength = min(0.95, 0.55 + (body2 / max(body1, 1e-9)) * 0.2 + (0.08 if vol_ok else 0))
        return {
            "pattern_name": "bullish_engulfing",
            "bias": "bull",
            "strength": float(strength),
            "confirmation": vol_ok,
            "bar_index": i,
        }

    # Bearish engulfing
    if c1 > o1 and c2 < o2 and o2 >= c1 and c2 <= o1:
        strength = min(0.95, 0.55 + (body2 / max(body1, 1e-9)) * 0.2 + (0.08 if vol_ok else 0))
        return {
            "pattern_name": "bearish_engulfing",
            "bias": "bear",
            "strength": float(strength),
            "confirmation": vol_ok,
            "bar_index": i,
        }

    # Hammer
    lower2 = _lower_wick(o2, l2, c2)
    upper2 = _upper_wick(o2, h2, c2)
    if lower2 >= body2 * 2.0 and upper2 <= body2 * 0.6 and (c2 - l2) / range2 > 0.55:
        strength = min(0.9, 0.5 + (lower2 / max(body2, 1e-9)) * 0.08 + (0.07 if vol_ok else 0))
        return {
            "pattern_name": "hammer",
            "bias": "bull",
            "strength": float(strength),
            "confirmation": vol_ok,
            "bar_index": i,
        }

    # Shooting star
    if upper2 >= body2 * 2.0 and lower2 <= body2 * 0.6 and (h2 - c2) / range2 > 0.55:
        strength = min(0.9, 0.5 + (upper2 / max(body2, 1e-9)) * 0.08 + (0.07 if vol_ok else 0))
        return {
            "pattern_name": "shooting_star",
            "bias": "bear",
            "strength": float(strength),
            "confirmation": vol_ok,
            "bar_index": i,
        }

    # Morning Star (3-candle pattern)
    # c0 is bearish, c1 is small, c2 is bullish and closes well into c0 body
    if c0 < o0 and body1 <= (max(h1 - l1, 1e-9) * 0.3) and c2 > o2:
        if min(c1, o1) < c0 and c2 > (c0 + o0) / 2:
            strength = min(0.98, 0.70 + (0.1 if vol_ok else 0))
            return {
                "pattern_name": "morning_star",
                "bias": "bull",
                "strength": float(strength),
                "confirmation": vol_ok,
                "bar_index": i,
            }

    # Evening Star (3-candle pattern)
    # c0 is bullish, c1 is small, c2 is bearish and closes well into c0 body
    if c0 > o0 and body1 <= (max(h1 - l1, 1e-9) * 0.3) and c2 < o2:
        if max(c1, o1) > c0 and c2 < (c0 + o0) / 2:
            strength = min(0.98, 0.70 + (0.1 if vol_ok else 0))
            return {
                "pattern_name": "evening_star",
                "bias": "bear",
                "strength": float(strength),
                "confirmation": vol_ok,
                "bar_index": i,
            }

    # Doji with slight directional bias using previous candle body
    doji_ratio = body2 / range2
    if doji_ratio <= 0.12:
        prev_bias: PatternBias = "bull" if c1 > o1 else "bear"
        strength = 0.52 + (0.06 if vol_ok else 0)
        return {
            "pattern_name": "doji",
            "bias": prev_bias,
            "strength": float(min(strength, 0.75)),
            "confirmation": vol_ok,
            "bar_index": i,
        }

    return None
