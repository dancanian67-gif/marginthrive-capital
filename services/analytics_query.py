"""Shared analytics query helpers — date ranges, shares, trends (Phase E2)."""

from __future__ import annotations

from constants.workflow import ANALYTICS_MAX_TREND_POINTS, ANALYTICS_OFFICER_LIMIT
from utils.db_compat import (
    datetime_filter_clause,
    distribution_share_percent,
    fill_daily_trend_series,
    rolling_period_days,
    safe_percentage,
)
from utils.resilience import warn_oversized_analytics_range


def analytics_range_span_days(range_key: str) -> int | None:
    return rolling_period_days(range_key)


def analytics_datetime_clause(range_key: str, column: str = "created_at") -> tuple[str, list]:
    warn_oversized_analytics_range(range_key)
    return datetime_filter_clause(range_key, column)


def add_distribution_shares(items: list[dict], total: int | None = None) -> list[dict]:
    denominator = total if total is not None else sum(item["count"] for item in items)
    denominator = denominator or 1
    for item in items:
        item["share"] = distribution_share_percent(item["count"], denominator)
    return items


def fill_daily_trend(rows: list[dict], range_key: str) -> list[dict]:
    return fill_daily_trend_series(rows, range_key)


def trend_query_limit() -> int:
    return ANALYTICS_MAX_TREND_POINTS


def officer_workload_limit() -> int:
    return ANALYTICS_OFFICER_LIMIT


def period_rejection_rate(rejected: int, total: int) -> float:
    return safe_percentage(rejected, max(total, 1))


def prepare_trend_chart(points: list[dict]) -> list[dict]:
    if not points:
        return []
    max_count = max(point["count"] for point in points) or 1
    prepared = []
    for point in points:
        label = point["label"]
        if len(label) == 10 and label[4] == "-":
            display_label = label[5:]
        else:
            display_label = label
        prepared.append(
            {
                "label": label,
                "display_label": display_label,
                "count": point["count"],
                "height_pct": safe_percentage(point["count"], max_count),
            }
        )
    return prepared
