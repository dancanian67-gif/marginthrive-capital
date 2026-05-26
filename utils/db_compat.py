"""Lightweight SQL dialect helpers — SQLite today, PostgreSQL-ready patterns (Phase E2).

Centralizes datetime filters, grouping, placeholders, and pagination so repositories
and services avoid scattered SQLite-specific fragments. PostgreSQL is not implemented yet.
"""

from __future__ import annotations

from datetime import date, timedelta

# Future migration hook: swap implementation when DIALECT == "postgresql"
DIALECT = "sqlite"


def sql_placeholders(count: int) -> str:
    if count <= 0:
        return ""
    return ", ".join("?" * count)


def datetime_filter_clause(range_key: str, column: str = "created_at") -> tuple[str, list]:
    """Return SQL AND fragment and bind params for an analytics time range."""
    if range_key == "all":
        return "", []
    if range_key == "today":
        return f" AND date({column}) = date('now')", []
    day_map = {"7d": 7, "30d": 30, "90d": 90}
    days = day_map.get(range_key)
    if days is None:
        return "", []
    return f" AND datetime({column}) >= datetime('now', '-{days} days')", []


def date_group_expression(column: str) -> str:
    return f"date({column})"


def day_label_select(column: str) -> str:
    return f"{date_group_expression(column)} AS day_label"


def datetime_order_expression(column: str) -> str:
    return f"datetime({column})"


def non_empty_timestamp_predicate(column: str) -> str:
    return f"{column} IS NOT NULL AND {column} != ''"


def rolling_period_days(range_key: str) -> int | None:
    if range_key == "today":
        return 1
    if range_key == "7d":
        return 7
    if range_key == "30d":
        return 30
    if range_key == "90d":
        return 90
    return None


def pagination_limit_offset(page: int, page_size: int) -> tuple[int, int]:
    safe_page = max(1, int(page or 1))
    safe_size = max(1, int(page_size or 1))
    return safe_size, (safe_page - 1) * safe_size


def safe_percentage(
    numerator: float | int,
    denominator: float | int,
    *,
    decimals: int = 1,
    default: float = 0.0,
) -> float:
    if not denominator:
        return default
    return round((float(numerator) / float(denominator)) * 100, decimals)


def fill_daily_trend_series(rows: list[dict], range_key: str, *, label_key: str = "label") -> list[dict]:
    """Fill missing calendar days with zero counts for bounded ranges."""
    span_days = rolling_period_days(range_key)
    if span_days is None:
        return [{label_key: row[label_key], "count": row["count"]} for row in rows]

    counts_by_day = {row[label_key]: row["count"] for row in rows}
    end_day = date.today()
    start_day = end_day - timedelta(days=span_days - 1)
    filled: list[dict] = []
    current = start_day
    while current <= end_day:
        key = current.isoformat()
        filled.append({label_key: key, "count": counts_by_day.get(key, 0)})
        current += timedelta(days=1)
    return filled


def distribution_share_percent(count: int, total: int | None = None, *, decimals: int = 1) -> float:
    denominator = total if total is not None else 0
    if denominator is None or denominator == 0:
        denominator = 1
    return safe_percentage(count, denominator, decimals=decimals)
