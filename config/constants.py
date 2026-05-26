"""
Trading Constants and Configuration — CoinDCX Futures advisor bot.
"""

# Internal timeframe keys used across the advisor pipeline
TIMEFRAMES = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}

TIMEFRAME_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}

# CoinDCX futures REST resolution (public candlesticks API, pcode=f)
COINDCX_REST_RESOLUTION: dict[str, str] = {
    "1m": "1",
    "5m": "5",
    "15m": "5",  # aggregated 3x5m
    "1h": "60",
    "4h": "60",  # aggregated 4x1h
    "1d": "1D",
}

# Advisor scan timeframes
ADVISOR_INTRADAY_TIMEFRAMES = ["15m", "1h"]
ADVISOR_SWING_TIMEFRAMES = ["4h", "1d"]

# Base symbols (pair built as B-{SYMBOL}_{MARGIN} per margin currency)
CRYPTO_PAIRS = {
    "BTC": "BTC",
    "ETH": "ETH",
    "SOL": "SOL",
    "BNB": "BNB",
    "XRP": "XRP",
    "ADA": "ADA",
    "AVAX": "AVAX",
    "DOGE": "DOGE",
    "LINK": "LINK",
    "POL": "POL",
    "LTC": "LTC",
    "BCH": "BCH",
    "ATOM": "ATOM",
    "NEAR": "NEAR",
    "DOT": "DOT",
    "UNI": "UNI",
    "APT": "APT",
    "ARB": "ARB",
    "OP": "OP",
    "INJ": "INJ",
    "SUI": "SUI",
    "TIA": "TIA",
    "SEI": "SEI",
    "FIL": "FIL",
    "AAVE": "AAVE",
    "RUNE": "RUNE",
}

MAJOR_SYMBOLS = frozenset({"BTC", "ETH", "SOL"})

# Technical Indicator Parameters
INDICATOR_PARAMS = {
    "RSI": {"period": 14, "overbought": 70, "oversold": 30},
    "MACD": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
    "BOLLINGER_BANDS": {"period": 20, "std_dev": 2},
    "STOCHASTIC": {"k_period": 14, "d_period": 3, "overbought": 80, "oversold": 20},
    "ATR": {"period": 14},
    "EMA": {"period": 21},
    "SMA": {"period": 50},
    # New indicators
    "ICHIMOKU": {
        "tenkan_period": 9,
        "kijun_period": 26,
        "senkou_b_period": 52,
        "displacement": 26,
    },
    "SUPERTREND": {"atr_period": 10, "multiplier": 3.0},
    "VWAP": {"std_dev_bands": [1, 2]},
    "OBV": {"signal_period": 10},
    "WILLIAMS_R": {"period": 14, "overbought": -20, "oversold": -80},
    "CCI": {"period": 20, "constant": 0.015},
    "FIBONACCI": {"swing_lookback": 50},
    "PIVOT_POINTS": {"methods": ["classic", "camarilla"]},
    "HEIKIN_ASHI": {"trend_lookback": 3},
    "ADX": {"period": 14, "trend_threshold": 25, "ranging_threshold": 20},
    # EMA stack
    "EMA_STACK": {"periods": [9, 21, 50, 200]},
}


# Risk Management Settings
RISK_MANAGEMENT = {
    "max_position_size_percent": 5.0,
    "min_position_size_percent": 1.0,
    "max_open_positions": 5,
    "default_stop_loss_percent": 2.0,
    "default_take_profit_percent": 5.0,
    "risk_reward_ratio": 1.5,
}

# Signal Weights (for combined strategy)
SIGNAL_WEIGHTS = {
    "RSI": 0.25,
    "MACD": 0.25,
    "BOLLINGER_BANDS": 0.25,
    "STOCHASTIC": 0.15,
    "LLM_SENTIMENT": 0.10,
}

# Trading Hours (UTC)
TRADING_HOURS = {
    "start": 0,  # 00:00 UTC
    "end": 24,   # 24:00 UTC (24/7 trading)
}

# Minimum Candle Requirements
MIN_CANDLES_FOR_ANALYSIS = {
    "5m": 50,
    "15m": 50,
    "1h": 50,
    "4h": 50,
    "1d": 30,
}

# API Rate Limiting
COINDCX_RATE_LIMITS = {
    "requests_per_second": 8,
    "min_interval_ms": 120,
}
