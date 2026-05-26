"""Delinquency intelligence helpers (Phase F1) — reuses loan servicing repayment data."""

from __future__ import annotations

import sqlite3
from datetime import date

from constants.collections import DELINQUENCY_BUCKET_LABELS, DELINQUENCY_BUCKETS
from constants.loans import DEFAULT_LOAN_LIFECYCLE_STATUS, REPAYMENT_RISK_LABELS
from repositories.collections import (
    _delinquency_bucket_sql,
    _delinquency_days_sql,
    collections_queue_predicate,
    fetch_collections_delinquency_distribution,
    fetch_collections_officer_workload,
    fetch_collections_queue_kpis,
)
from services.loans import delinquency_context


def delinquency_bucket_from_days(days_overdue: int, *, lifecycle: str = "") -> str:
    if lifecycle in ("completed", "written_off", "not_issued"):
        return "current"
    if days_overdue <= 0:
        return "current"
    if days_overdue <= 30:
        return "1_30_days"
    if days_overdue <= 60:
        return "31_60_days"
    if days_overdue <= 90:
        return "61_90_days"
    return "90_plus_days"


def delinquency_bucket_label(bucket: str) -> str:
    return DELINQUENCY_BUCKET_LABELS.get(bucket, bucket.replace("_", " ").title())


def repayment_risk_score(application: sqlite3.Row | dict) -> int:
    """Lightweight 0–100 score from lifecycle, overdue days, and repayment risk level."""
    lifecycle = application.get("loan_lifecycle_status") if isinstance(application, dict) else application["loan_lifecycle_status"]
    lifecycle = lifecycle or DEFAULT_LOAN_LIFECYCLE_STATUS
    ctx = delinquency_context(application)
    risk = (
        application.get("repayment_risk_level")
        if isinstance(application, dict)
        else application["repayment_risk_level"]
    ) or "current"

    score = 0
    if lifecycle == "defaulted":
        score += 45
    elif lifecycle == "overdue":
        score += 35
    elif ctx["is_delinquent"]:
        score += 20

    days = ctx["days_overdue"]
    if days >= 90:
        score += 35
    elif days >= 61:
        score += 28
    elif days >= 31:
        score += 18
    elif days >= 1:
        score += 10

    if risk == "critical":
        score += 25
    elif risk == "elevated":
        score += 15
    elif risk == "watch":
        score += 5

    coll_risk = (
        application.get("collections_risk_level")
        if isinstance(application, dict)
        else application["collections_risk_level"]
    ) or "routine"
    if coll_risk == "legal":
        score += 20
    elif coll_risk == "critical":
        score += 15
    elif coll_risk == "elevated":
        score += 8

    return min(100, score)


def missed_payment_indicator(application: sqlite3.Row | dict) -> bool:
    observations = (
        application.get("missed_payment_observations")
        if isinstance(application, dict)
        else application["missed_payment_observations"]
    ) or ""
    if observations.strip():
        return True
    ctx = delinquency_context(application)
    outstanding = (
        application.get("outstanding_balance")
        if isinstance(application, dict)
        else application["outstanding_balance"]
    )
    return ctx["is_delinquent"] and outstanding is not None and float(outstanding) > 0


def enrich_collections_queue_row(row: sqlite3.Row | dict) -> dict:
    data = dict(row) if not isinstance(row, dict) else dict(row)
    if "days_overdue" not in data or data.get("days_overdue") is None:
        ctx = delinquency_context(data)
        data["days_overdue"] = ctx["days_overdue"]
    bucket = data.get("delinquency_bucket") or delinquency_bucket_from_days(
        int(data.get("days_overdue") or 0),
        lifecycle=data.get("loan_lifecycle_status") or "",
    )
    data["delinquency_bucket"] = bucket
    data["delinquency_bucket_label"] = delinquency_bucket_label(bucket)
    data["repayment_risk_score"] = repayment_risk_score(data)
    data["missed_payment_flag"] = missed_payment_indicator(data)
    data["follow_up_due"] = _follow_up_is_due(data.get("collections_next_follow_up"))
    return data


def enrich_collections_queue_row_with_intelligence(
    row: sqlite3.Row | dict,
    intelligence_context: dict | None = None,
) -> dict:
    """Full queue enrichment: delinquency + intelligence priority."""
    from services.collections_followup import assess_account_followup, queue_aging_indicator
    from services.collections_priority import attach_priority_intelligence

    data = enrich_collections_queue_row(row)
    ctx = intelligence_context or {}
    attach_priority_intelligence(
        data,
        repayment_count=ctx.get("repayment_count", 0),
        escalation_count=ctx.get("escalation_count", 0),
        recent_payment_amount=ctx.get("recent_payment_amount", 0.0),
    )
    followup = assess_account_followup(data)
    data["followup"] = followup
    data["queue_aging_label"] = queue_aging_indicator(int(data.get("days_overdue") or 0))
    summary = (intelligence_context or {}).get("promise_summary")
    if summary:
        active = summary.get("active_promise")
        data["has_active_promise"] = active is not None
        if active:
            data["active_promise"] = active
            promise_day = (active.get("promise_date") or "")[:10]
            data["promise_overdue"] = bool(promise_day and promise_day < date.today().isoformat())
        data["broken_promise_count"] = summary.get("broken_count", 0)
    return data


def _follow_up_is_due(follow_up_raw: str | None) -> bool:
    raw = (follow_up_raw or "").strip()
    if not raw:
        return False
    try:
        return date.fromisoformat(raw[:10]) <= date.today()
    except ValueError:
        return False


def build_collections_analytics_package(cursor, range_key: str) -> dict:
    """Aggregate delinquency metrics for overview, analytics, and reports."""
    from services.collections_recovery_analytics import build_collections_recovery_package

    kpis = fetch_collections_queue_kpis(cursor)
    distribution = fetch_collections_delinquency_distribution(cursor)
    officer_workload = fetch_collections_officer_workload(cursor)
    recovery_package = build_collections_recovery_package(cursor, range_key)
    from services.promise_analytics import build_promise_analytics_package

    promise_package = build_promise_analytics_package(cursor, range_key)
    total_cases = kpis["queue_total"] or 1
    for item in distribution:
        item["share"] = round((item["count"] / total_cases) * 100, 1)

    high_risk = sum(
        item["count"]
        for item in distribution
        if item.get("bucket") in {"61_90_days", "90_plus_days"}
    )
    return {
        "kpis": kpis,
        "delinquency_distribution": distribution,
        "officer_workload": officer_workload,
        "high_risk_delinquency_count": high_risk,
        "range_key": range_key,
        "recovery": recovery_package,
        "promises": promise_package,
    }


def collections_insights(package: dict) -> list[str]:
    from services.collections_recovery_analytics import recovery_analytics_insights
    from services.promise_analytics import promise_analytics_insights

    kpis = package["kpis"]
    insights: list[str] = []
    if package.get("recovery"):
        insights.extend(recovery_analytics_insights(package["recovery"]))
    if package.get("promises"):
        insights.extend(promise_analytics_insights(package["promises"]))
    if kpis["queue_total"]:
        insights.append(
            f"{kpis['queue_total']} accounts in the collections queue "
            f"(${kpis['total_exposure']:,.0f} outstanding exposure)."
        )
    if kpis["follow_up_due_count"]:
        insights.append(
            f"{kpis['follow_up_due_count']} cases have follow-ups due or overdue today."
        )
    if kpis["urgent_count"]:
        insights.append(f"{kpis['urgent_count']} urgent-priority collections cases require attention.")
    if kpis["legal_count"]:
        insights.append(f"{kpis['legal_count']} accounts are in legal escalation status.")
    if package.get("high_risk_delinquency_count"):
        insights.append(
            f"{package['high_risk_delinquency_count']} accounts are 61+ days past due."
        )
    return insights[:5]


__all__ = [
    "DELINQUENCY_BUCKETS",
    "delinquency_bucket_from_days",
    "delinquency_bucket_label",
    "repayment_risk_score",
    "missed_payment_indicator",
    "enrich_collections_queue_row",
    "build_collections_analytics_package",
    "collections_insights",
    "delinquency_context",
    "collections_queue_predicate",
    "_delinquency_days_sql",
    "_delinquency_bucket_sql",
]
