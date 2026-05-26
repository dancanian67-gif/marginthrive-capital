"""Operational notification resilience warnings (Phase G1) — log-only."""

from __future__ import annotations

from constants.ops import (
    NOTIFICATION_BACKLOG_WARN,
    NOTIFICATION_CRITICAL_UNRESOLVED_WARN,
    NOTIFICATION_GOVERNANCE_SPIKE_WARN,
)
from repositories.notifications import (
    count_excessive_notification_backlog,
    count_unresolved_critical_notifications,
)
from utils.ops_logging import log_operational_warning


def run_notification_operational_warnings(cursor) -> None:
    critical_unresolved = count_unresolved_critical_notifications(cursor)
    if critical_unresolved >= NOTIFICATION_CRITICAL_UNRESOLVED_WARN:
        log_operational_warning(
            "Excessive unresolved critical operational notifications",
            critical_unresolved=critical_unresolved,
            threshold=NOTIFICATION_CRITICAL_UNRESOLVED_WARN,
        )

    backlog = count_excessive_notification_backlog(cursor, threshold=NOTIFICATION_BACKLOG_WARN)
    if backlog:
        log_operational_warning(
            "Large unacknowledged notification backlog",
            unacknowledged_total=backlog,
            threshold=NOTIFICATION_BACKLOG_WARN,
        )

    cursor.execute(
        """
        SELECT COUNT(*) FROM operational_events
        WHERE governance_tag IS NOT NULL AND governance_tag != ''
          AND created_at >= datetime('now', '-7 days')
        """
    )
    gov_spike = cursor.fetchone()[0] or 0
    if gov_spike >= NOTIFICATION_GOVERNANCE_SPIKE_WARN:
        log_operational_warning(
            "Elevated governance-tagged operational events in last 7 days",
            governance_events=gov_spike,
            threshold=NOTIFICATION_GOVERNANCE_SPIKE_WARN,
        )
