"""
Validators - Input validation utilities
"""

from typing import Union, List
from datetime import datetime
import re


def validate_symbol(symbol: str) -> bool:
    """Validate cryptocurrency symbol format"""
    from config.crypto_list import SUPPORTED_CRYPTOS
    return symbol in SUPPORTED_CRYPTOS


def validate_timeframe(timeframe: str) -> bool:
    """Validate trading timeframe"""
    valid_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"]
    return timeframe in valid_timeframes


def validate_percentage(value: float, name: str = "value") -> bool:
    """Validate percentage value (0-100)"""
    if not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    if value < 0 or value > 100:
        raise ValueError(f"{name} must be between 0 and 100")
    return True


def validate_price(price: float) -> bool:
    """Validate price format"""
    if not isinstance(price, (int, float)):
        raise ValueError("Price must be a number")
    if price < 0:
        raise ValueError("Price cannot be negative")
    return True


def validate_quantity(quantity: float) -> bool:
    """Validate quantity format"""
    if not isinstance(quantity, (int, float)):
        raise ValueError("Quantity must be a number")
    if quantity <= 0:
        raise ValueError("Quantity must be positive")
    return True


def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_json_path(path: str) -> bool:
    """Validate JSON path format"""
    # Simple validation for "key.subkey" format
    parts = path.split(".")
    return all(part.replace("_", "").isalnum() for part in parts)


def validate_trading_pair(pair: str) -> bool:
    """Validate trading pair format (e.g., BTCUSDT)"""
    pattern = r'^[A-Z]{2,}[A-Z]{3,}$'  # At least 2 letters + at least 3 letters
    return bool(re.match(pattern, pair))


def validate_api_key(key: str) -> bool:
    """Validate API key format (basic check)"""
    return len(key) > 20 and key.isalnum()


class ValidationError(Exception):
    """Custom validation error"""
    pass
