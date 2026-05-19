"""
Helper Functions - General utility functions
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import json
from decimal import Decimal


def format_timestamp(timestamp: int, unit: str = "ms") -> datetime:
    """
    Convert timestamp to datetime object
    
    Args:
        timestamp: Unix timestamp
        unit: "ms" for milliseconds, "s" for seconds
    """
    if unit == "ms":
        return datetime.fromtimestamp(timestamp / 1000)
    return datetime.fromtimestamp(timestamp)


def get_timestamp_ms() -> int:
    """Get current timestamp in milliseconds"""
    return int(datetime.utcnow().timestamp() * 1000)


def get_timestamp_s() -> int:
    """Get current timestamp in seconds"""
    return int(datetime.utcnow().timestamp())


def round_price(price: float, decimals: int = 2) -> float:
    """Round price to specified decimals"""
    return round(price, decimals)


def round_quantity(quantity: float, decimals: int = 8) -> float:
    """Round quantity to specified decimals"""
    return round(quantity, decimals)


def calculate_percentage_change(old: float, new: float) -> float:
    """Calculate percentage change between two values"""
    if old == 0:
        return 0
    return ((new - old) / abs(old)) * 100


def calculate_profit_loss(entry_price: float, exit_price: float, quantity: float) -> float:
    """Calculate P&L for a trade"""
    return (exit_price - entry_price) * quantity


def calculate_roi_percent(entry_price: float, exit_price: float) -> float:
    """Calculate ROI percentage"""
    return ((exit_price - entry_price) / entry_price) * 100


def deep_merge_dicts(base: Dict, update: Dict) -> Dict:
    """Deep merge dictionaries"""
    for key, value in update.items():
        if isinstance(value, dict):
            base[key] = deep_merge_dicts(base.get(key, {}), value)
        else:
            base[key] = value
    return base


def flatten_dict(d: Dict, parent_key: str = "", sep: str = ".") -> Dict:
    """Flatten nested dictionary"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def truncate_string(s: str, length: int = 100) -> str:
    """Truncate string to specified length"""
    if len(s) <= length:
        return s
    return s[:length - 3] + "..."


def format_number(num: float, decimals: int = 2) -> str:
    """Format number with comma separators"""
    return f"{num:,.{decimals}f}"


def safe_json_parse(data: str, default: Any = None) -> Any:
    """Safely parse JSON string"""
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(obj: Any, indent: int = None) -> str:
    """Safely convert object to JSON string"""
    try:
        return json.dumps(obj, indent=indent, default=str)
    except TypeError:
        return str(obj)


def get_min_max(values: List[float]) -> tuple:
    """Get min and max from list of values"""
    if not values:
        return None, None
    return min(values), max(values)


def calculate_average(values: List[float]) -> float:
    """Calculate average of values"""
    if not values:
        return 0
    return sum(values) / len(values)


def calculate_standard_deviation(values: List[float]) -> float:
    """Calculate standard deviation"""
    if len(values) < 2:
        return 0
    mean = calculate_average(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return variance ** 0.5
