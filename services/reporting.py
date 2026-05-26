from flask import url_for

from constants.analytics import ANALYTICS_TIME_RANGES
from constants.workflow import APPLICATION_RISK_LEVELS, APPLICATION_STATUSES
from repositories.applications import (
    fetch_executive_kpis,
    fetch_fraud_review_summary,
    fetch_risk_distribution,
    fetch_status_distribution,
)
from repositories.loans import fetch_loan_lifecycle_distribution
from repositories.underwriting import fetch_underwriting_portfolio_distribution
from repositories.audit import fetch_governance_audit_summary
from services.analytics import (
    fetch_analytics_activity_summary,
    fetch_analytics_backlog_snapshot,
    fetch_analytics_distribution,
    fetch_analytics_officer_workload,
    fetch_analytics_period_kpis,
    fetch_analytics_pipeline_distribution,
)
from services.analytics_query import add_distribution_shares, period_rejection_rate
from services.delinquency import build_collections_analytics_package, collections_insights
from services.portfolio_intelligence import (
    build_portfolio_intelligence_package,
    portfolio_export_metric_rows,
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
    portfolio_underwriting = fetch_underwriting_portfolio_distribution(cursor)
    portfolio_loans = fetch_loan_lifecycle_distribution(cursor)
    total_portfolio = portfolio_kpis["total_applications"] or 1
    add_distribution_shares(portfolio_status, total_portfolio)
    add_distribution_shares(portfolio_risk, total_portfolio)

    outcome_summary = {
        "portfolio_approved": portfolio_kpis["approved"],
        "portfolio_rejected": portfolio_kpis["rejected"],
        "portfolio_pipeline": portfolio_kpis["active_pipeline"],
        "period_approved": period_kpis["approved"],
        "period_rejected": period_kpis["rejected"],
        "period_pipeline": period_kpis["active_pipeline"],
        "period_total": period_kpis["total_applications"],
    }
    outcome_summary["period_rejection_rate"] = period_rejection_rate(
        period_kpis["rejected"],
        period_kpis["total_applications"],
    )

    portfolio_intelligence = build_portfolio_intelligence_package(cursor, range_key)
    collections_analytics = build_collections_analytics_package(cursor, range_key)
    from services.notification_analytics import (
        build_notification_analytics_package,
        notification_analytics_insights,
    )

    notifications_analytics = build_notification_analytics_package(cursor, range_key)

    executive_lines = report_executive_summary(
        portfolio_kpis,
        period_kpis,
        backlog,
        governance,
        ANALYTICS_TIME_RANGES[range_key],
    )
    executive_lines.extend(portfolio_intelligence["insights"][:3])
    executive_lines.extend(collections_insights(collections_analytics)[:2])
    executive_lines.extend(notification_analytics_insights(notifications_analytics)[:2])
    executive_lines = executive_lines[:8]

    return {
        "portfolio_kpis": portfolio_kpis,
        "period_kpis": period_kpis,
        "status_distribution": status_distribution,
        "risk_distribution": risk_distribution,
        "pipeline_distribution": pipeline_distribution,
        "portfolio_status": portfolio_status,
        "portfolio_risk": portfolio_risk,
        "portfolio_underwriting": portfolio_underwriting,
        "portfolio_loans": portfolio_loans,
        "officer_workload": officer_workload,
        "backlog": backlog,
        "activity_summary": activity_summary,
        "governance": governance,
        "fraud_summary": fraud_summary,
        "outcome_summary": outcome_summary,
        "executive_lines": executive_lines,
        "portfolio_intelligence": portfolio_intelligence,
        "collections_analytics": collections_analytics,
        "notifications_analytics": notifications_analytics,
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
        "repayments": url_for("admin_export_repayments", **filter_params),
        "portfolio": url_for("admin_export_report", report_type="portfolio", **range_params),
        "collections_delinquent": url_for("admin_export_collections_delinquent"),
        "collections_activity": url_for("admin_export_collections_activity", **range_params),
        "collections_workload": url_for("admin_export_collections_workload"),
        "collections_exposure": url_for("admin_export_collections_exposure"),
        "collections_recovery_summary": url_for("admin_export_collections_recovery_summary"),
        "collections_escalation_report": url_for("admin_export_collections_escalation_report"),
        "collections_officer_recovery": url_for("admin_export_collections_officer_recovery"),
        "collections_aging_movement": url_for("admin_export_collections_aging_movement"),
        "collections_outcome_distribution": url_for("admin_export_collections_outcome_distribution"),
        "promises_active": url_for("admin_export_promises_active"),
        "promises_broken": url_for("admin_export_promises_broken"),
        "promises_overdue": url_for("admin_export_promises_overdue"),
        "promises_officer_performance": url_for("admin_export_promises_officer_performance"),
        "promises_repayment_conversion": url_for("admin_export_promises_repayment_conversion"),
        "notifications_alerts": url_for("admin_export_notifications_alerts"),
        "notifications_unresolved": url_for("admin_export_notifications_unresolved"),
        "notifications_governance": url_for("admin_export_notifications_governance"),
        "notifications_ack_metrics": url_for("admin_export_notifications_ack_metrics"),
        "notifications_critical_events": url_for("admin_export_notifications_critical_events"),
    }
