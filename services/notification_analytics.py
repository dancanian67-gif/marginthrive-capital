"""Notification and operational event analytics (Phase G1)."""

from __future__ import annotations

from repositories.notifications import fetch_notification_analytics_metrics


def build_notification_analytics_package(cursor, range_key: str) -> dict:
    metrics = fetch_notification_analytics_metrics(cursor, range_key)
    return {"metrics": metrics, "range_key": range_key}


def notification_analytics_insights(package: dict) -> list[str]:
    metrics = package.get("metrics") or {}
    insights: list[str] = []
    if metrics.get("unresolved_period"):
        insights.append(
            f"{metrics['unresolved_period']} operational notification(s) remain unacknowledged in period."
        )
    if metrics.get("aging_critical_unresolved"):
        insights.append(
            f"{metrics['aging_critical_unresolved']} critical notification(s) are older than 3 days."
        )
    if metrics.get("governance_alerts_period"):
        insights.append(
            f"{metrics['governance_alerts_period']} governance-tagged alert(s) recorded in period."
        )
    rate = metrics.get("acknowledgement_rate_pct")
    if rate is not None and metrics.get("total_period", 0) > 0:
        insights.append(f"Operator acknowledgement rate: {rate}% in period.")
    return insights[:4]
