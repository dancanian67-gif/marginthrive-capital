from constants.analytics import ANALYTICS_TIME_RANGES, DEFAULT_ANALYTICS_RANGE
from utils.db_compat import datetime_filter_clause


def parse_analytics_range(args) -> str:
    range_key = (args.get("range") or DEFAULT_ANALYTICS_RANGE).strip()
    if range_key not in ANALYTICS_TIME_RANGES:
        return DEFAULT_ANALYTICS_RANGE
    return range_key


def analytics_datetime_clause(range_key: str, column: str = "created_at") -> tuple[str, list]:
    """Backward-compatible wrapper; prefer services.analytics_query in new code."""
    return datetime_filter_clause(range_key, column)
