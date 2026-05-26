"""Computed operational alerts and backlog sync (Phase G1) — awareness only."""

from __future__ import annotations

from constants.collections import COLLECTIONS_CRITICAL_STATUSES
from repositories.collections import fetch_collections_queue_kpis
from repositories.collections_intelligence import (
    count_stale_critical_risk_accounts,
    count_unresolved_legal_escalations,
)
from repositories.notifications import has_recent_notification
from services.operational_events import emit_operational_event


def build_operational_alert_banners(cursor) -> list[dict]:
    """Non-persistent alert banners for the notification center UI."""
    alerts: list[dict] = []
    kpis = fetch_collections_queue_kpis(cursor)

    if kpis["urgent_count"]:
        alerts.append(
            {
                "severity": "critical",
                "title": "Urgent collections cases",
                "message": f"{kpis['urgent_count']} urgent-priority accounts need review.",
            }
        )
    if kpis["follow_up_due_count"]:
        alerts.append(
            {
                "severity": "warning",
                "title": "Overdue follow-ups",
                "message": f"{kpis['follow_up_due_count']} collections follow-ups are due or overdue.",
            }
        )
    legal = count_unresolved_legal_escalations(cursor)
    if legal:
        alerts.append(
            {
                "severity": "critical",
                "title": "Unresolved legal escalations",
                "message": f"{legal} account(s) remain in legal escalation.",
            }
        )
    stale = count_stale_critical_risk_accounts(cursor, 14)
    if stale:
        alerts.append(
            {
                "severity": "warning",
                "title": "Stale critical-risk accounts",
                "message": f"{stale} critical-risk case(s) without recent contact.",
            }
        )

    cursor.execute(
        """
        SELECT COUNT(*) FROM applications
        WHERE risk_level IN ('High', 'Critical')
          AND (assigned_officer IS NULL OR assigned_officer = '')
          AND status NOT IN ('Rejected', 'Closed')
        """
    )
    unassigned_high_risk = cursor.fetchone()[0] or 0
    if unassigned_high_risk:
        alerts.append(
            {
                "severity": "warning",
                "title": "High-risk unassigned applications",
                "message": f"{unassigned_high_risk} high/critical risk application(s) lack an assigned officer.",
            }
        )

    cursor.execute(
        """
        SELECT COUNT(*) FROM applications
        WHERE underwriting_status = 'escalated_review'
          AND (reviewed_at IS NULL OR reviewed_at < datetime('now', '-14 days'))
        """
    )
    stale_uw = cursor.fetchone()[0] or 0
    if stale_uw:
        alerts.append(
            {
                "severity": "warning",
                "title": "Stale underwriting reviews",
                "message": f"{stale_uw} escalated underwriting review(s) need attention.",
            }
        )

    cursor.execute(
        """
        SELECT application_id, COUNT(*) AS c FROM recovery_promises
        WHERE promise_status = 'broken'
        GROUP BY application_id
        HAVING c >= 2
        """
    )
    repeat_broken = len(cursor.fetchall())
    if repeat_broken:
        alerts.append(
            {
                "severity": "critical",
                "title": "Repeated broken promises",
                "message": f"{repeat_broken} account(s) have multiple broken recovery commitments.",
            }
        )

    return alerts[:8]


def sync_operational_alert_notifications(cursor, *, actor: str = "system-ops") -> int:
    """
    Emit deduplicated notifications for persistent operational alert conditions.
    Returns count of new notifications created.
    """
    created = 0
    kpis = fetch_collections_queue_kpis(cursor)
    queue_total = kpis["queue_total"] or 1
    if kpis["follow_up_due_count"] and kpis["follow_up_due_count"] / queue_total >= 0.25:
        if not has_recent_notification(cursor, event_category="overdue_followup", application_id=None):
            emit_operational_event(
                event_category="overdue_followup",
                severity="warning",
                title="Elevated overdue follow-up volume",
                message=(
                    f"{kpis['follow_up_due_count']} of {queue_total} queue cases have due follow-ups."
                ),
                actor=actor,
                cursor=cursor,
            )
            created += 1

    cursor.execute(
        f"""
        SELECT id, collections_status, collections_assigned_to FROM applications
        WHERE collections_status IN ({",".join("?" * len(COLLECTIONS_CRITICAL_STATUSES))})
          AND collections_status != 'resolved'
        LIMIT 50
        """,
        tuple(COLLECTIONS_CRITICAL_STATUSES),
    )
    for row in cursor.fetchall():
        app_id = row["id"]
        if has_recent_notification(
            cursor, event_category="critical_risk", application_id=app_id, days=14
        ):
            continue
        emit_operational_event(
            event_category="critical_risk",
            severity="critical",
            title="Unresolved critical collections account",
            message=f"Application #{app_id} is in {row['collections_status']} status.",
            application_id=app_id,
            actor=actor,
            target_username=row["collections_assigned_to"],
            cursor=cursor,
        )
        created += 1

    cursor.execute(
        """
        SELECT application_id FROM recovery_promises
        WHERE promise_status = 'broken'
        GROUP BY application_id
        HAVING COUNT(*) >= 2
        """
    )
    for row in cursor.fetchall():
        app_id = row["application_id"]
        if has_recent_notification(cursor, event_category="broken_promise", application_id=app_id, days=30):
            continue
        emit_operational_event(
            event_category="broken_promise",
            severity="critical",
            title="Repeated broken recovery commitments",
            message=f"Application #{app_id} has multiple broken promises.",
            application_id=app_id,
            actor=actor,
            cursor=cursor,
        )
        created += 1

    return created
