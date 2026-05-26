"""Collections operational resilience warnings (Phase F2) — log-only."""

from __future__ import annotations

from constants.ops import (
    COLLECTIONS_CRITICAL_QUEUE_WARN,
    COLLECTIONS_DELINQUENCY_GROWTH_WARN_RATIO,
    COLLECTIONS_QUEUE_WARN_SIZE,
    COLLECTIONS_STALE_FOLLOW_UP_DAYS,
    COLLECTIONS_WRITEOFF_SPIKE_WARN,
)
from repositories.collections import fetch_collections_queue_kpis
from repositories.collections_intelligence import (
    count_stale_critical_risk_accounts,
    count_unresolved_legal_escalations,
    count_writeoff_recommendations_recent,
)
from utils.ops_logging import log_operational_warning


def warn_collections_queue_size(queue_total: int) -> None:
    if queue_total >= COLLECTIONS_QUEUE_WARN_SIZE:
        log_operational_warning(
            "Collections queue exceeds recommended size",
            queue_total=queue_total,
            threshold=COLLECTIONS_QUEUE_WARN_SIZE,
            hint="Review prioritization and officer assignments.",
        )


def warn_critical_tier_backlog(cursor) -> None:
    from repositories.collections import collections_queue_predicate

    predicate = collections_queue_predicate("a")
    cursor.execute(
        f"""
        SELECT COUNT(*) FROM applications a
        WHERE {predicate}
          AND collections_risk_level IN ('critical', 'legal')
          AND collections_status NOT IN ('resolved')
        """
    )
    count = cursor.fetchone()[0] or 0
    if count >= COLLECTIONS_CRITICAL_QUEUE_WARN:
        log_operational_warning(
            "Elevated count of unresolved critical-risk collections accounts",
            critical_risk_count=count,
            threshold=COLLECTIONS_CRITICAL_QUEUE_WARN,
        )


def warn_stale_followups(cursor, follow_up_due_count: int, queue_total: int) -> None:
    if queue_total <= 0:
        return
    ratio = follow_up_due_count / queue_total
    if ratio >= COLLECTIONS_DELINQUENCY_GROWTH_WARN_RATIO:
        log_operational_warning(
            "High proportion of collections follow-ups are due or overdue",
            follow_up_due_count=follow_up_due_count,
            queue_total=queue_total,
            ratio=round(ratio, 2),
        )

    stale_critical = count_stale_critical_risk_accounts(cursor, COLLECTIONS_STALE_FOLLOW_UP_DAYS)
    if stale_critical:
        log_operational_warning(
            "Stale critical-risk collections accounts without recent contact",
            stale_count=stale_critical,
            stale_days=COLLECTIONS_STALE_FOLLOW_UP_DAYS,
        )


def warn_legal_escalation_backlog(cursor) -> None:
    unresolved = count_unresolved_legal_escalations(cursor)
    if unresolved:
        log_operational_warning(
            "Unresolved legal escalation cases in active queue",
            unresolved_legal_count=unresolved,
        )


def warn_writeoff_spike(cursor) -> None:
    recent = count_writeoff_recommendations_recent(cursor, days=30)
    if recent >= COLLECTIONS_WRITEOFF_SPIKE_WARN:
        log_operational_warning(
            "Elevated write-off recommendations in last 30 days",
            writeoff_recommendations=recent,
            threshold=COLLECTIONS_WRITEOFF_SPIKE_WARN,
        )


def run_collections_operational_warnings(cursor) -> None:
    """Emit structured warnings for collections ops health (non-fatal)."""
    from utils.promise_resilience import run_promise_operational_warnings
    kpis = fetch_collections_queue_kpis(cursor)
    queue_total = kpis["queue_total"]
    warn_collections_queue_size(queue_total)
    warn_critical_tier_backlog(cursor)
    warn_stale_followups(cursor, kpis["follow_up_due_count"], queue_total)
    warn_legal_escalation_backlog(cursor)
    warn_writeoff_spike(cursor)
    run_promise_operational_warnings(cursor)
