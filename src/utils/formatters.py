"""
Data formatters - Output formatting utilities
"""

from typing import Any, Dict, List
from decimal import Decimal


def format_currency(value: float, symbol: str = "$", decimals: int = 2) -> str:
    """Format value as currency"""
    return f"{symbol}{value:,.{decimals}f}"


def format_percent(value: float, decimals: int = 2, include_sign: bool = True) -> str:
    """Format value as percentage"""
    sign = "+" if include_sign and value > 0 else ""
    return f"{sign}{value:.{decimals}f}%"


def format_crypto_price(price: float, symbol: str = "BTC") -> str:
    """Format cryptocurrency price"""
    if price >= 1000:
        return f"${price:,.2f}"
    elif price >= 1:
        return f"${price:.4f}"
    else:
        return f"${price:.8f}"


def format_dataframe(df) -> str:
    """Format pandas dataframe for display"""
    return df.to_string(index=False)


def format_list_table(data: List[Dict], headers: List[str] = None) -> str:
    """Format list of dicts as table"""
    if not data:
        return "No data"

    if headers is None:
        headers = list(data[0].keys())

    # Calculate column widths
    col_widths = {}
    for header in headers:
        col_widths[header] = len(str(header))
        for row in data:
            col_widths[header] = max(
                col_widths[header],
                len(str(row.get(header, "")))
            )

    # Format header
    header_line = " | ".join(
        str(h).ljust(col_widths[h]) for h in headers
    )
    separator = "-" * len(header_line)

    # Format rows
    rows = [header_line, separator]
    for row in data:
        row_line = " | ".join(
            str(row.get(h, "")).ljust(col_widths[h]) for h in headers
        )
        rows.append(row_line)

    return "\n".join(rows)
