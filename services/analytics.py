from constants.workflow import (
    APPLICATION_RISK_LEVELS,
    APPLICATION_STATUSES,
    KPI_ACTIVE_PIPELINE_STATUSES,
    KPI_APPROVED_STATUSES,
    KPI_HIGH_RISK_LEVELS,
    KPI_REJECTED_STATUS,
)
from repositories.applications import fetch_pipeline_backlog
from services.analytics_query import (
    add_distribution_shares,
    analytics_datetime_clause,
    analytics_range_span_days,
    distribution_share_percent,
    fill_daily_trend,
    officer_workload_limit,
    period_rejection_rate,
    prepare_trend_chart,
    trend_query_limit,
)
from utils.db_compat import day_label_select, non_empty_timestamp_predicate, sql_placeholders

# Re-export for templates and routes that import from services.analytics
__all__ = [
    "analytics_range_span_days",
    "add_distribution_shares",
    "fill_daily_trend",
    "prepare_trend_chart",
    "fetch_analytics_period_kpis",
    "fetch_analytics_intake_trend",
    "fetch_analytics_outcome_trend",
    "fetch_analytics_fraud_trend",
    "fetch_analytics_distribution",
    "fetch_analytics_pipeline_distribution",
    "fetch_analytics_officer_workload",
    "fetch_analytics_backlog_snapshot",
    "fetch_analytics_activity_summary",
    "analytics_insights",
    "analytics_range_query",
]


def fetch_analytics_period_kpis(cursor, range_key: str) -> dict:
    created_clause, created_params = analytics_datetime_clause(range_key, "created_at")
    pipeline_ph = sql_placeholders(len(KPI_ACTIVE_PIPELINE_STATUSES))
    approved_ph = sql_placeholders(len(KPI_APPROVED_STATUSES))
    high_risk_ph = sql_placeholders(len(KPI_HIGH_RISK_LEVELS))

    cursor.execute(
        f"""
        SELECT
            COUNT(*) AS total_applications,
            SUM(CASE WHEN status IN ({pipeline_ph}) THEN 1 ELSE 0 END) AS active_pipeline,
            SUM(CASE WHEN status IN ({approved_ph}) THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) AS rejected,
            SUM(CASE WHEN risk_level IN ({high_risk_ph}) THEN 1 ELSE 0 END) AS high_risk,
            SUM(CASE WHEN flagged_fraud = 1 THEN 1 ELSE 0 END) AS fraud_flagged
        FROM applications
        WHERE {non_empty_timestamp_predicate('created_at')}{created_clause}
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
        SELECT {day_label_select('created_at')}, COUNT(*) AS count
        FROM applications
        WHERE {non_empty_timestamp_predicate('created_at')}{created_clause}
        GROUP BY date(created_at)
        ORDER BY day_label ASC
        LIMIT ?
        """,
        (*created_params, trend_query_limit()),
    )
    rows = [{"label": row["day_label"], "count": row["count"]} for row in cursor.fetchall()]
    return prepare_trend_chart(fill_daily_trend(rows, range_key))


def fetch_analytics_outcome_trend(cursor, range_key: str) -> list[dict]:
    created_clause, created_params = analytics_datetime_clause(range_key, "created_at")
    approved_ph = sql_placeholders(len(KPI_APPROVED_STATUSES))
    pipeline_ph = sql_placeholders(len(KPI_ACTIVE_PIPELINE_STATUSES))
    cursor.execute(
        f"""
        SELECT
            {day_label_select('created_at')},
            SUM(CASE WHEN status IN ({approved_ph}) THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) AS rejected,
            SUM(CASE WHEN status IN ({pipeline_ph}) THEN 1 ELSE 0 END) AS pipeline
        FROM applications
        WHERE {non_empty_timestamp_predicate('created_at')}{created_clause}
        GROUP BY date(created_at)
        ORDER BY day_label ASC
        LIMIT ?
        """,
        (
            *KPI_APPROVED_STATUSES,
            KPI_REJECTED_STATUS,
            *KPI_ACTIVE_PIPELINE_STATUSES,
            *created_params,
            trend_query_limit(),
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
        SELECT {day_label_select('created_at')}, COUNT(*) AS count
        FROM applications
        WHERE flagged_fraud = 1
          AND {non_empty_timestamp_predicate('created_at')}{created_clause}
        GROUP BY date(created_at)
        ORDER BY day_label ASC
        LIMIT ?
        """,
        (*created_params, trend_query_limit()),
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
        WHERE {non_empty_timestamp_predicate('created_at')}{created_clause}
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
    pipeline_ph = sql_placeholders(len(KPI_ACTIVE_PIPELINE_STATUSES))
    cursor.execute(
        f"""
        SELECT status AS label, COUNT(*) AS count
        FROM applications
        WHERE status IN ({pipeline_ph})
          AND {non_empty_timestamp_predicate('created_at')}{created_clause}
        GROUP BY status
        ORDER BY count DESC
        """,
        (*KPI_ACTIVE_PIPELINE_STATUSES, *created_params),
    )
    return add_distribution_shares([{"label": row["label"], "count": row["count"]} for row in cursor.fetchall()])


def fetch_analytics_officer_workload(cursor, range_key: str) -> list[dict]:
    created_clause, created_params = analytics_datetime_clause(range_key, "created_at")
    pipeline_ph = sql_placeholders(len(KPI_ACTIVE_PIPELINE_STATUSES))
    cursor.execute(
        f"""
        SELECT
            CASE
                WHEN assigned_officer IS NULL OR TRIM(assigned_officer) = ''
                THEN 'Unassigned'
                ELSE assigned_officer
            END AS officer_label,
            COUNT(*) AS total_count,
            SUM(CASE WHEN status IN ({pipeline_ph}) THEN 1 ELSE 0 END) AS pipeline_count,
            SUM(CASE WHEN flagged_fraud = 1 THEN 1 ELSE 0 END) AS fraud_count
        FROM applications
        WHERE {non_empty_timestamp_predicate('created_at')}{created_clause}
        GROUP BY officer_label
        ORDER BY pipeline_count DESC, total_count DESC, officer_label COLLATE NOCASE ASC
        LIMIT ?
        """,
        (*KPI_ACTIVE_PIPELINE_STATUSES, *created_params, officer_workload_limit()),
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
        row["load_share"] = distribution_share_percent(row["pipeline_count"], max_pipeline)
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
        WHERE {non_empty_timestamp_predicate('created_at')}{updated_clause}
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
            f"Rejection rate in period: {period_rejection_rate(period_kpis['rejected'], period_kpis['total_applications'])}%."
        )
    if not pipeline_distribution and period_kpis["total_applications"] == 0:
        insights.append("No applications were created in the selected time range.")
    return insights[:5]


def analytics_range_query(range_key: str) -> dict:
    return {"range": range_key}
