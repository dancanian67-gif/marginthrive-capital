from flask import url_for

from constants.analytics import ANALYTICS_TIME_RANGES
from constants.workflow import APPLICATION_RISK_LEVELS, APPLICATION_STATUSES
from repositories.applications import (
    fetch_executive_kpis,
    fetch_fraud_review_summary,
    fetch_risk_distribution,
    fetch_status_distribution,
)
from repositories.audit import fetch_governance_audit_summary
from services.analytics import (
    fetch_analytics_activity_summary,
    fetch_analytics_backlog_snapshot,
    fetch_analytics_distribution,
    fetch_analytics_officer_workload,
    fetch_analytics_period_kpis,
    fetch_analytics_pipeline_distribution,
)


def report_executive_summary(
    portfolio_kpis: dict,
    period_kpis: dict,
    backlog: dict,
    governance: dict,
    range_label: str,
) -> list[str]:
    lines = [
        f"Reporting period: {range_label}.",
        (
            f"Portfolio: {portfolio_kpis['total_applications']} applications, "
            f"{portfolio_kpis['active_pipeline']} in active pipeline, "
            f"{portfolio_kpis['fraud_flagged']} fraud-flagged."
        ),
        (
            f"Period intake: {period_kpis['total_applications']} created; "
            f"{period_kpis['approved']} approved-stage, {period_kpis['rejected']} rejected, "
            f"{period_kpis['high_risk']} high/critical risk."
        ),
    ]
    if backlog["bottleneck_stage"]:
        lines.append(
            f"Live backlog bottleneck: {backlog['bottleneck_stage']} "
            f"({backlog['bottleneck_count']} cases)."
        )
    if governance["workflow_batches"]:
        lines.append(
            f"Governance: {governance['workflow_batches']} workflow batches, "
            f"{governance['critical_events']} critical audit events in period."
        )
    return lines[:6]


def build_reports_page_data(cursor, range_key: str) -> dict:
    portfolio_kpis = fetch_executive_kpis(cursor)
    period_kpis = fetch_analytics_period_kpis(cursor, range_key)
    status_distribution = fetch_analytics_distribution(
        cursor, range_key, group_column="status", order_values=APPLICATION_STATUSES
    )
    risk_distribution = fetch_analytics_distribution(
        cursor, range_key, group_column="risk_level", order_values=APPLICATION_RISK_LEVELS
    )
    pipeline_distribution = fetch_analytics_pipeline_distribution(cursor, range_key)
    officer_workload = fetch_analytics_officer_workload(cursor, range_key)
    backlog = fetch_analytics_backlog_snapshot(cursor)
    activity_summary = fetch_analytics_activity_summary(cursor, range_key)
    governance = fetch_governance_audit_summary(cursor, range_key)
    fraud_summary = fetch_fraud_review_summary(cursor)

    portfolio_status = fetch_status_distribution(cursor)
    portfolio_risk = fetch_risk_distribution(cursor)
    total_portfolio = portfolio_kpis["total_applications"] or 1
    for item in portfolio_status:
        item["share"] = round((item["count"] / total_portfolio) * 100, 1)
    for item in portfolio_risk:
        item["share"] = round((item["count"] / total_portfolio) * 100, 1)

    outcome_summary = {
        "portfolio_approved": portfolio_kpis["approved"],
        "portfolio_rejected": portfolio_kpis["rejected"],
        "portfolio_pipeline": portfolio_kpis["active_pipeline"],
        "period_approved": period_kpis["approved"],
        "period_rejected": period_kpis["rejected"],
        "period_pipeline": period_kpis["active_pipeline"],
        "period_total": period_kpis["total_applications"],
    }
    if period_kpis["total_applications"]:
        outcome_summary["period_rejection_rate"] = round(
            (period_kpis["rejected"] / period_kpis["total_applications"]) * 100,
            1,
        )
    else:
        outcome_summary["period_rejection_rate"] = 0.0

    executive_lines = report_executive_summary(
        portfolio_kpis,
        period_kpis,
        backlog,
        governance,
        ANALYTICS_TIME_RANGES[range_key],
    )

    return {
        "portfolio_kpis": portfolio_kpis,
        "period_kpis": period_kpis,
        "status_distribution": status_distribution,
        "risk_distribution": risk_distribution,
        "pipeline_distribution": pipeline_distribution,
        "portfolio_status": portfolio_status,
        "portfolio_risk": portfolio_risk,
        "officer_workload": officer_workload,
        "backlog": backlog,
        "activity_summary": activity_summary,
        "governance": governance,
        "fraud_summary": fraud_summary,
        "outcome_summary": outcome_summary,
        "executive_lines": executive_lines,
    }


def report_export_urls(range_key: str, filter_query: dict | None = None) -> dict[str, str]:
    range_params = {"range": range_key}
    filter_params = {**(filter_query or {}), **range_params}
    return {
        "operational": url_for("admin_export_report", report_type="operational", **range_params),
        "pipeline": url_for("admin_export_report", report_type="pipeline", **range_params),
        "outcomes": url_for("admin_export_report", report_type="outcomes", **range_params),
        "risk": url_for("admin_export_report", report_type="risk", **range_params),
        "fraud": url_for("admin_export_report", report_type="fraud", **range_params),
        "officers": url_for("admin_export_report", report_type="officers", **range_params),
        "backlog": url_for("admin_export_report", report_type="backlog", **range_params),
        "audit": url_for("admin_export_audit", **range_params),
        "applications_filtered": url_for("admin_export_applications", **filter_params),
        "applications_all": url_for("admin_export_applications", **range_params),
    }
