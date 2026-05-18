from datetime import date, timedelta

from constants.analytics import ANALYTICS_MAX_TREND_POINTS, ANALYTICS_OFFICER_LIMIT
from constants.workflow import (
    APPLICATION_RISK_LEVELS,
    APPLICATION_STATUSES,
    KPI_ACTIVE_PIPELINE_STATUSES,
    KPI_APPROVED_STATUSES,
    KPI_HIGH_RISK_LEVELS,
    KPI_REJECTED_STATUS,
)
from repositories.applications import fetch_pipeline_backlog
from utils.time_range import analytics_datetime_clause, parse_analytics_range

def analytics_range_span_days(range_key: str) -> int | None:
    if range_key == "today":
        return 1
    if range_key == "7d":
        return 7
    if range_key == "30d":
        return 30
    if range_key == "90d":
        return 90
    return None


def add_distribution_shares(items: list[dict], total: int | None = None) -> list[dict]:
    denominator = total if total is not None else sum(item["count"] for item in items)
    denominator = denominator or 1
    for item in items:
        item["share"] = round((item["count"] / denominator) * 100, 1)
    return items


def fill_daily_trend(rows: list[dict], range_key: str) -> list[dict]:
    span_days = analytics_range_span_days(range_key)
    if span_days is None:
        return [{"label": row["label"], "count": row["count"]} for row in rows]

    counts_by_day = {row["label"]: row["count"] for row in rows}
    end_day = date.today()
    start_day = end_day - timedelta(days=span_days - 1)
    filled: list[dict] = []
    current = start_day
    while current <= end_day:
        key = current.isoformat()
        filled.append({"label": key, "count": counts_by_day.get(key, 0)})
        current += timedelta(days=1)
    return filled


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
                "height_pct": round((point["count"] / max_count) * 100, 1),
            }
        )
    return prepared


def fetch_analytics_period_kpis(cursor, range_key: str) -> dict:
    created_clause, created_params = analytics_datetime_clause(range_key, "created_at")
    pipeline_placeholders = ", ".join("?" * len(KPI_ACTIVE_PIPELINE_STATUSES))
    approved_placeholders = ", ".join("?" * len(KPI_APPROVED_STATUSES))
    high_risk_placeholders = ", ".join("?" * len(KPI_HIGH_RISK_LEVELS))

    cursor.execute(
        f"""
        SELECT
            COUNT(*) AS total_applications,
            SUM(CASE WHEN status IN ({pipeline_placeholders}) THEN 1 ELSE 0 END) AS active_pipeline,
            SUM(CASE WHEN status IN ({approved_placeholders}) THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) AS rejected,
            SUM(CASE WHEN risk_level IN ({high_risk_placeholders}) THEN 1 ELSE 0 END) AS high_risk,
            SUM(CASE WHEN flagged_fraud = 1 THEN 1 ELSE 0 END) AS fraud_flagged
        FROM applications
        WHERE created_at IS NOT NULL AND created_at != ''{created_clause}
        """,
        (
            *KPI_ACTIVE_PIPELINE_STATUSES,
            *KPI_APPROVED_STATUSES,
            KPI_REJECTED_STATUS,
            *KPI_HIGH_RISK_LEVELS,
            *created_params,
        ),
    )
    row = cursor.fetchone()
    return {
        "total_applications": row["total_applications"] or 0,
        "active_pipeline": row["active_pipeline"] or 0,
        "approved": row["approved"] or 0,
        "rejected": row["rejected"] or 0,
        "high_risk": row["high_risk"] or 0,
        "fraud_flagged": row["fraud_flagged"] or 0,
    }


def fetch_analytics_intake_trend(cursor, range_key: str) -> list[dict]:
    created_clause, created_params = analytics_datetime_clause(range_key, "created_at")
    cursor.execute(
        f"""
        SELECT date(created_at) AS day_label, COUNT(*) AS count
        FROM applications
        WHERE created_at IS NOT NULL AND created_at != ''{created_clause}
        GROUP BY date(created_at)
        ORDER BY day_label ASC
        LIMIT ?
        """,
        (*created_params, ANALYTICS_MAX_TREND_POINTS),
    )
    rows = [{"label": row["day_label"], "count": row["count"]} for row in cursor.fetchall()]
    return prepare_trend_chart(fill_daily_trend(rows, range_key))


def fetch_analytics_outcome_trend(cursor, range_key: str) -> list[dict]:
    created_clause, created_params = analytics_datetime_clause(range_key, "created_at")
    approved_placeholders = ", ".join("?" * len(KPI_APPROVED_STATUSES))
    pipeline_placeholders = ", ".join("?" * len(KPI_ACTIVE_PIPELINE_STATUSES))
    cursor.execute(
        f"""
        SELECT
            date(created_at) AS day_label,
            SUM(CASE WHEN status IN ({approved_placeholders}) THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) AS rejected,
            SUM(CASE WHEN status IN ({pipeline_placeholders}) THEN 1 ELSE 0 END) AS pipeline
        FROM applications
        WHERE created_at IS NOT NULL AND created_at != ''{created_clause}
        GROUP BY date(created_at)
        ORDER BY day_label ASC
        LIMIT ?
        """,
        (
            *KPI_APPROVED_STATUSES,
            KPI_REJECTED_STATUS,
            *KPI_ACTIVE_PIPELINE_STATUSES,
            *created_params,
            ANALYTICS_MAX_TREND_POINTS,
        ),
    )
    return [
        {
            "label": row["day_label"],
            "approved": row["approved"] or 0,
            "rejected": row["rejected"] or 0,
            "pipeline": row["pipeline"] or 0,
        }
        for row in cursor.fetchall()
    ]


def fetch_analytics_fraud_trend(cursor, range_key: str) -> list[dict]:
    created_clause, created_params = analytics_datetime_clause(range_key, "created_at")
    cursor.execute(
        f"""
        SELECT date(created_at) AS day_label, COUNT(*) AS count
        FROM applications
        WHERE flagged_fraud = 1
          AND created_at IS NOT NULL AND created_at != ''{created_clause}
        GROUP BY date(created_at)
        ORDER BY day_label ASC
        LIMIT ?
        """,
        (*created_params, ANALYTICS_MAX_TREND_POINTS),
    )
    rows = [{"label": row["day_label"], "count": row["count"]} for row in cursor.fetchall()]
    return prepare_trend_chart(fill_daily_trend(rows, range_key))


def fetch_analytics_distribution(
    cursor,
    range_key: str,
    *,
    group_column: str,
    order_values: tuple[str, ...] | None = None,
) -> list[dict]:
    created_clause, created_params = analytics_datetime_clause(range_key, "created_at")
    cursor.execute(
        f"""
        SELECT {group_column} AS label, COUNT(*) AS count
        FROM applications
        WHERE created_at IS NOT NULL AND created_at != ''{created_clause}
        GROUP BY {group_column}
        ORDER BY count DESC, label COLLATE NOCASE ASC
        """,
        created_params,
    )
    items = [{"label": row["label"] or "Unknown", "count": row["count"]} for row in cursor.fetchall()]
    if order_values:
        order_index = {value: index for index, value in enumerate(order_values)}
        items.sort(key=lambda item: (order_index.get(item["label"], len(order_values)), -item["count"]))
    return add_distribution_shares(items)


def fetch_analytics_pipeline_distribution(cursor, range_key: str) -> list[dict]:
    created_clause, created_params = analytics_datetime_clause(range_key, "created_at")
    pipeline_placeholders = ", ".join("?" * len(KPI_ACTIVE_PIPELINE_STATUSES))
    cursor.execute(
        f"""
        SELECT status AS label, COUNT(*) AS count
        FROM applications
        WHERE status IN ({pipeline_placeholders})
          AND created_at IS NOT NULL AND created_at != ''{created_clause}
        GROUP BY status
        ORDER BY count DESC
        """,
        (*KPI_ACTIVE_PIPELINE_STATUSES, *created_params),
    )
    return add_distribution_shares([{"label": row["label"], "count": row["count"]} for row in cursor.fetchall()])


def fetch_analytics_officer_workload(cursor, range_key: str) -> list[dict]:
    created_clause, created_params = analytics_datetime_clause(range_key, "created_at")
    pipeline_placeholders = ", ".join("?" * len(KPI_ACTIVE_PIPELINE_STATUSES))
    cursor.execute(
        f"""
        SELECT
            CASE
                WHEN assigned_officer IS NULL OR TRIM(assigned_officer) = ''
                THEN 'Unassigned'
                ELSE assigned_officer
            END AS officer_label,
            COUNT(*) AS total_count,
            SUM(CASE WHEN status IN ({pipeline_placeholders}) THEN 1 ELSE 0 END) AS pipeline_count,
            SUM(CASE WHEN flagged_fraud = 1 THEN 1 ELSE 0 END) AS fraud_count
        FROM applications
        WHERE created_at IS NOT NULL AND created_at != ''{created_clause}
        GROUP BY officer_label
        ORDER BY pipeline_count DESC, total_count DESC, officer_label COLLATE NOCASE ASC
        LIMIT ?
        """,
        (*KPI_ACTIVE_PIPELINE_STATUSES, *created_params, ANALYTICS_OFFICER_LIMIT),
    )
    rows = [
        {
            "officer": row["officer_label"],
            "total_count": row["total_count"],
            "pipeline_count": row["pipeline_count"],
            "fraud_count": row["fraud_count"],
        }
        for row in cursor.fetchall()
    ]
    if not rows:
        return rows
    max_pipeline = max(row["pipeline_count"] for row in rows) or 1
    for row in rows:
        row["load_share"] = round((row["pipeline_count"] / max_pipeline) * 100, 1)
    return rows


def fetch_analytics_backlog_snapshot(cursor) -> dict:
    pipeline_backlog = fetch_pipeline_backlog(cursor)
    pipeline_total = sum(item["count"] for item in pipeline_backlog)
    bottleneck = pipeline_backlog[0] if pipeline_backlog else None
    return {
        "pipeline_backlog": add_distribution_shares(pipeline_backlog, pipeline_total),
        "pipeline_total": pipeline_total,
        "bottleneck_stage": bottleneck["label"] if bottleneck else None,
        "bottleneck_count": bottleneck["count"] if bottleneck else 0,
    }


def fetch_analytics_activity_summary(cursor, range_key: str) -> dict:
    updated_clause, updated_params = analytics_datetime_clause(range_key, "created_at")
    cursor.execute(
        f"""
        SELECT COUNT(DISTINCT batch_id) AS updates_in_period
        FROM workflow_history
        WHERE created_at IS NOT NULL AND created_at != ''{updated_clause}
        """,
        updated_params,
    )
    updates_in_period = cursor.fetchone()["updates_in_period"] or 0
    return {"updates_in_period": updates_in_period}


def analytics_insights(
    period_kpis: dict,
    backlog: dict,
    officer_workload: list[dict],
    pipeline_distribution: list[dict],
) -> list[str]:
    insights: list[str] = []
    if backlog["bottleneck_stage"] and backlog["bottleneck_count"]:
        insights.append(
            f"Largest pipeline bottleneck: {backlog['bottleneck_stage']} "
            f"({backlog['bottleneck_count']} cases)."
        )
    if officer_workload:
        top = officer_workload[0]
        if top["officer"] != "Unassigned" and top["pipeline_count"] > 0:
            insights.append(
                f"Highest active pipeline load: {top['officer']} ({top['pipeline_count']} cases)."
            )
        unassigned = next((row for row in officer_workload if row["officer"] == "Unassigned"), None)
        if unassigned and unassigned["pipeline_count"] > 0:
            insights.append(
                f"{unassigned['pipeline_count']} pipeline cases remain unassigned to an officer."
            )
    if period_kpis["fraud_flagged"]:
        insights.append(
            f"{period_kpis['fraud_flagged']} applications flagged for fraud in this period."
        )
    if period_kpis["high_risk"]:
        insights.append(
            f"{period_kpis['high_risk']} high-risk or critical applications created in this period."
        )
    if period_kpis["active_pipeline"] and period_kpis["rejected"]:
        insights.append(
            f"Rejection rate in period: "
            f"{round((period_kpis['rejected'] / max(period_kpis['total_applications'], 1)) * 100, 1)}%."
        )
    if not pipeline_distribution and period_kpis["total_applications"] == 0:
        insights.append("No applications were created in the selected time range.")
    return insights[:5]


def analytics_range_query(range_key: str) -> dict:
    return {"range": range_key}
