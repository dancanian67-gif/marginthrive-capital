"""Recovery analytics expansion (Phase F2)."""

from __future__ import annotations

from services.analytics_query import analytics_datetime_clause
from repositories.collections import fetch_collections_delinquency_distribution, fetch_collections_queue_kpis
from repositories.collections_intelligence import (
    fetch_collections_resolution_trend,
    fetch_escalation_distribution,
    fetch_officer_recovery_performance,
    fetch_recovery_outcome_distribution,
    fetch_recovery_summary_metrics,
    fetch_repayment_recovery_velocity,
)


def build_collections_recovery_package(cursor, range_key: str) -> dict:
    """Extended collections intelligence for analytics, reports, and overview."""
    range_clause, range_params = analytics_datetime_clause(range_key, "ch.created_at")

    kpis = fetch_collections_queue_kpis(cursor)
    recovery = fetch_recovery_summary_metrics(cursor, range_clause, range_params)
    resolution_trend = fetch_collections_resolution_trend(cursor, range_clause, range_params)
    escalation_distribution = fetch_escalation_distribution(cursor)
    officer_recovery = fetch_officer_recovery_performance(cursor)
    aging_distribution = fetch_collections_delinquency_distribution(cursor)
    outcome_distribution = fetch_recovery_outcome_distribution(cursor)
    velocity = fetch_repayment_recovery_velocity(cursor)

    return {
        "kpis": kpis,
        "recovery": recovery,
        "resolution_trend": resolution_trend,
        "escalation_distribution": escalation_distribution,
        "officer_recovery": officer_recovery,
        "aging_distribution": aging_distribution,
        "outcome_distribution": outcome_distribution,
        "velocity": velocity,
        "range_key": range_key,
        "promise_to_pay_tracking": {
            "active_promises": recovery["promise_to_pay_count"],
            "note": "Promise-to-pay accounts tracked for future automation.",
        },
    }


def recovery_analytics_insights(package: dict) -> list[str]:
    insights: list[str] = []
    recovery = package.get("recovery", {})
    velocity = package.get("velocity", {})

    if recovery.get("recovery_rate_pct") is not None:
        insights.append(
            f"Queue recovery rate (resolved / queue): {recovery['recovery_rate_pct']}%."
        )
    if recovery.get("period_resolutions"):
        insights.append(
            f"{recovery['period_resolutions']} resolution events recorded in the selected period."
        )
    if recovery.get("writeoff_exposure", 0) > 0:
        insights.append(
            f"Write-off recommended exposure: ${recovery['writeoff_exposure']:,.0f}."
        )
    if velocity.get("total_recovered_30d", 0) > 0:
        insights.append(
            f"${velocity['total_recovered_30d']:,.0f} recovered via repayments in the last 30 days."
        )
    if recovery.get("promise_to_pay_count"):
        insights.append(
            f"{recovery['promise_to_pay_count']} accounts in promise-to-pay status."
        )
    return insights[:6]
