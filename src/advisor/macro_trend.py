"""BTC macro trend guard — block counter-trend shorts on alts."""

from __future__ import annotations

from typing import Literal, Optional

from config.settings import settings
from src.data.models import CandleList
from src.planitt.mtf_confluence import _htf_side

Direction = Literal["BUY", "SELL"]


def _side_at_timestamp(candle_list: CandleList, ts_ms: int, *, min_bars: int = 50) -> Optional[str]:
    candles = [c for c in candle_list.candles if c.timestamp <= ts_ms]
    if len(candles) < min_bars:
        return None
    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    price = closes[-1]
    side = _htf_side(closes, highs, lows, price)
    return side


def btc_macro_bearish(
    btc_htf: dict[str, CandleList],
    ts_ms: int,
) -> tuple[bool, str | None]:
    """True when BTC 4h and 1d both read bearish at signal time."""
    if not settings.ADVISOR_REQUIRE_BTC_BEAR_FOR_SELL:
        return True, None

    required = ("4h", "1d")
    for tf in required:
        series = btc_htf.get(tf)
        if series is None:
            return False, f"btc_macro_missing_{tf}"
        side = _side_at_timestamp(series, ts_ms)
        if side is None:
            return False, f"btc_macro_missing_{tf}"
        if side != "SELL":
            return False, f"btc_macro_not_bear_{tf}"

    return True, None


def btc_macro_bullish_strict(
    btc_htf: dict[str, CandleList],
    ts_ms: int,
) -> tuple[bool, str | None]:
    """Swing BUY on alts: BTC 4h and 1d must both read bullish."""
    if not btc_htf:
        return False, "btc_macro_data_missing"

    for tf in ("4h", "1d"):
        series = btc_htf.get(tf)
        if series is None:
            return False, f"btc_macro_missing_{tf}"
        side = _side_at_timestamp(series, ts_ms)
        if side is None:
            return False, f"btc_macro_missing_{tf}"
        if side != "BUY":
            return False, f"btc_macro_not_bull_{tf}"

    return True, None


def btc_macro_bullish(
    btc_htf: dict[str, CandleList],
    ts_ms: int,
) -> tuple[bool, str | None]:
    """True when BTC 4h and 1d both read bullish at signal time."""
    if not settings.ADVISOR_REQUIRE_BTC_BULL_FOR_BUY:
        return True, None

    if not btc_htf:
        return False, "btc_macro_data_missing"

    required = ("1d",)
    for tf in required:
        series = btc_htf.get(tf)
        if series is None:
            return False, f"btc_macro_missing_{tf}"
        side = _side_at_timestamp(series, ts_ms)
        if side is None:
            return False, f"btc_macro_missing_{tf}"
        if side != "BUY":
            return False, f"btc_macro_not_bull_{tf}"

    return True, None


def macro_alignment_score(
    side: Direction,
    btc_htf: dict,
    ts_ms: int,
) -> float:
    """
    Soft BTC macro score in [-1, +1] for the signal direction.
    +1 = strongly aligned with BTC 4h/1d; -1 = counter-macro.
    """
    from src.data.models import CandleList

    if not btc_htf:
        return 0.0

    votes: list[float] = []
    for tf in ("4h", "1d"):
        series = btc_htf.get(tf)
        if series is None or not isinstance(series, CandleList):
            continue
        s = _side_at_timestamp(series, ts_ms)
        if s is None:
            continue
        votes.append(1.0 if s == "BUY" else -1.0)
    if not votes:
        return 0.0
    raw = sum(votes) / len(votes)
    return raw if side == "BUY" else -raw


def validate_direction_for_timeframe(
    side: Direction,
    timeframe: str,
    symbol: str,
) -> tuple[bool, str | None]:
    """SELL only on allowed swing timeframes per SOP + performance tuning."""
    if side != "SELL":
        return True, None

    allowed = settings.advisor_sell_allowed_timeframes
    if side == "SELL":
        if not allowed:
            return False, "sell_direction_blocked"
        if timeframe not in allowed:
            return False, f"sell_tf_not_allowed_{timeframe}"

    return True, None


def validate_macro_for_signal(
    *,
    symbol: str,
    side: Direction,
    timeframe: str,
    signal_ts_ms: int,
    btc_htf: dict[str, CandleList] | None,
) -> tuple[bool, str | None]:
    ok_tf, tf_reason = validate_direction_for_timeframe(side, timeframe, symbol)
    if not ok_tf:
        return False, tf_reason

    if side != "SELL" or symbol == "BTC":
        if side == "BUY" and symbol != "BTC":
            if timeframe in ("4h", "1d") and settings.ADVISOR_REQUIRE_BTC_BULL_FOR_SWING_BUY:
                return btc_macro_bullish_strict(btc_htf or {}, signal_ts_ms)
            if settings.ADVISOR_REQUIRE_BTC_BULL_FOR_BUY:
                return btc_macro_bullish(btc_htf or {}, signal_ts_ms)
        return True, None

    if not btc_htf:
        return False, "btc_macro_data_missing"

    return btc_macro_bearish(btc_htf, signal_ts_ms)
