"""
Formatters
Utility functions for formatting data and results
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any


def format_currency(value: float, currency: str = "$") -> str:
    """
    Format a number as currency.

    Args:
        value: Numeric value to format
        currency: Currency symbol (default: "$")

    Returns:
        Formatted currency string
    """
    if value is None:
        return f"{currency}0.00"
    return f"{currency}{value:,.2f}"


def format_percentage(value: float) -> str:
    """Format a number as percentage"""
    if value is None:
        return "0.0%"
    return f"{value:.1f}%"


def format_number(value: float, decimals: int = 0) -> str:
    """Format a number with thousands separator"""
    if value is None:
        return "0"
    if decimals == 0:
        return f"{int(value):,}"
    return f"{value:,.{decimals}f}"


def format_date(value: date | datetime) -> str:
    """
    Format a date or datetime for display.

    Args:
        value: Date or datetime object

    Returns:
        Formatted date string (empty string if None)
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return value.strftime("%Y-%m-%d")


def serialize_value(value: Any) -> Any:
    """Serialize a value for JSON response"""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def format_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Format query results for API response.
    Handles serialization of special types.

    Args:
        results: List of result dictionaries

    Returns:
        Formatted results with serialized values
    """
    formatted = []
    for row in results:
        formatted_row = {}
        for key, value in row.items():
            formatted_row[key] = serialize_value(value)
        formatted.append(formatted_row)
    return formatted


def get_result_columns(results: list[dict[str, Any]]) -> list[str]:
    """Extract column names from results"""
    if not results:
        return []
    return list(results[0].keys())


def format_sql_for_display(sql: str) -> str:
    """
    Format SQL for readable display.
    Adds proper indentation and line breaks.
    """
    formatted = sql.strip()

    # Add newlines before major keywords
    for keyword in ["FROM", "WHERE", "GROUP BY", "ORDER BY", "HAVING", "LIMIT"]:
        formatted = formatted.replace(f" {keyword} ", f"\n{keyword} ")

    # Add newlines and indentation for JOINs
    for join_type in ["LEFT JOIN", "INNER JOIN", "RIGHT JOIN", "JOIN"]:
        formatted = formatted.replace(f" {join_type} ", f"\n  {join_type} ")

    # Add newlines for AND/OR in WHERE clause
    formatted = formatted.replace(" AND ", "\n  AND ")
    formatted = formatted.replace(" OR ", "\n  OR ")

    return formatted


def summarize_results(results: list[dict[str, Any]], limit: int = 5) -> str:
    """
    Create a text summary of query results.

    Args:
        results: Query results
        limit: Max rows to show

    Returns:
        Human-readable summary
    """
    if not results:
        return "No results found."

    total_rows = len(results)
    columns = list(results[0].keys())

    summary_parts = [f"Found {total_rows} result(s) with columns: {', '.join(columns)}", ""]

    for i, row in enumerate(results[:limit]):
        row_parts = [f"{k}: {serialize_value(v)}" for k, v in row.items()]
        summary_parts.append(f"  {i+1}. {', '.join(row_parts)}")

    if total_rows > limit:
        summary_parts.append(f"  ... and {total_rows - limit} more rows")

    return "\n".join(summary_parts)


def infer_column_type(column_name: str, sample_values: list[Any]) -> str:
    """
    Infer the display type of a column based on name and values.

    Returns one of: currency, percentage, number, date, text
    """
    name_lower = column_name.lower()

    # Check column name patterns
    if any(
        s in name_lower
        for s in ["revenue", "sales", "total", "subtotal", "price", "amount", "fee", "tip", "cost"]
    ):
        return "currency"

    if any(s in name_lower for s in ["percent", "pct", "rate", "ratio"]):
        return "percentage"

    if any(s in name_lower for s in ["count", "quantity", "num", "number"]):
        return "number"

    if any(s in name_lower for s in ["date", "time", "created", "updated"]):
        return "date"

    # Check value types
    for value in sample_values:
        if value is not None:
            if isinstance(value, date | datetime):
                return "date"
            if isinstance(value, int | float | Decimal):
                return "number"
            break

    return "text"


def format_column_value(value: Any, column_type: str) -> str:
    """Format a value based on its inferred column type"""
    if value is None:
        return ""

    if column_type == "currency":
        return format_currency(float(value))
    elif column_type == "percentage":
        return format_percentage(float(value))
    elif column_type == "number":
        if isinstance(value, float) and value != int(value):
            return format_number(value, 2)
        return format_number(value, 0)
    elif column_type == "date":
        if isinstance(value, date | datetime):
            return format_date(value)
        return str(value)
    else:
        return str(value)
