from constants.analytics import ANALYTICS_TIME_RANGES, DEFAULT_ANALYTICS_RANGE


def parse_analytics_range(args) -> str:
    range_key = (args.get("range") or DEFAULT_ANALYTICS_RANGE).strip()
    if range_key not in ANALYTICS_TIME_RANGES:
        return DEFAULT_ANALYTICS_RANGE
    return range_key


def analytics_datetime_clause(range_key: str, column: str = "created_at") -> tuple[str, list]:
    if range_key == "all":
        return "", []
    if range_key == "today":
        return f" AND date({column}) = date('now')", []
    day_map = {"7d": 7, "30d": 30, "90d": 90}
    days = day_map[range_key]
    return f" AND datetime({column}) >= datetime('now', '-{days} days')", []
