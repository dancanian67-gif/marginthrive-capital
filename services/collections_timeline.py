"""Collections activity timeline (Phase F2) — grouped, categorized, append-only."""

from __future__ import annotations

from constants.collections import (
    COLLECTIONS_STATUS_LABELS,
    STATUS_TO_TIMELINE_CATEGORY,
    TIMELINE_CATEGORY_CONTACT,
    TIMELINE_CATEGORY_ESCALATION,
    TIMELINE_CATEGORY_GENERAL,
    TIMELINE_CATEGORY_LABELS,
    TIMELINE_CATEGORY_LEGAL,
    TIMELINE_CATEGORY_PROMISE,
    TIMELINE_CATEGORY_REPAYMENT,
    TIMELINE_CATEGORY_WRITEOFF,
)
from constants.promises import PROMISE_STATUS_LABELS


def _category_for_history_row(row) -> str:
    status = row["collections_status"] or ""
    if status in STATUS_TO_TIMELINE_CATEGORY:
        return STATUS_TO_TIMELINE_CATEGORY[status]
    action = (row["action_type"] or "").lower()
    if "contact" in action:
        return TIMELINE_CATEGORY_GENERAL
    if "escalation" in action or row["is_critical"]:
        return TIMELINE_CATEGORY_ESCALATION
    if status == "legal_escalation":
        return TIMELINE_CATEGORY_LEGAL
    if status == "write_off_recommended":
        return TIMELINE_CATEGORY_WRITEOFF
    return TIMELINE_CATEGORY_GENERAL


def _recovery_badge(status: str, is_critical: bool) -> str:
    if status == "resolved":
        return "Recovered"
    if status == "write_off_recommended":
        return "Write-off review"
    if status == "legal_escalation":
        return "Legal"
    if status == "promise_to_pay":
        return "Promise"
    if status == "recovery_active":
        return "Recovery active"
    if is_critical:
        return "Critical"
    if status in ("escalated_review",):
        return "Escalated"
    return "Active"


def build_collections_activity_timeline(
    history_rows: list,
    repayment_rows: list | None = None,
    promise_history_rows: list | None = None,
) -> dict:
    """Build grouped timeline with categories and operator summary."""
    events: list[dict] = []

    for row in history_rows:
        category = _category_for_history_row(row)
        status = row["collections_status"]
        events.append(
            {
                "source": "collections_history",
                "created_at": row["created_at"],
                "actor": row["actor"],
                "category": category,
                "category_label": TIMELINE_CATEGORY_LABELS.get(category, category),
                "headline": COLLECTIONS_STATUS_LABELS.get(status, status),
                "collections_status": status,
                "context_notes": row["context_notes"] or "",
                "is_critical": bool(row["is_critical"]),
                "recovery_badge": _recovery_badge(status, bool(row["is_critical"])),
                "batch_id": row["batch_id"],
            }
        )

    for row in promise_history_rows or []:
        status = row["promise_status"]
        events.append(
            {
                "source": "recovery_promise_history",
                "created_at": row["created_at"],
                "actor": row["actor"],
                "category": TIMELINE_CATEGORY_PROMISE,
                "category_label": TIMELINE_CATEGORY_LABELS[TIMELINE_CATEGORY_PROMISE],
                "headline": f"Promise {PROMISE_STATUS_LABELS.get(status, status)} — {row['promise_amount']}",
                "collections_status": None,
                "context_notes": row["context_notes"] or "",
                "is_critical": bool(row["is_critical"]),
                "recovery_badge": PROMISE_STATUS_LABELS.get(status, status),
                "batch_id": row["batch_id"],
            }
        )

    for payment in repayment_rows or []:
        events.append(
            {
                "source": "repayment",
                "created_at": payment["created_at"] or payment["payment_date"],
                "actor": payment["actor"] or "—",
                "category": TIMELINE_CATEGORY_REPAYMENT,
                "category_label": TIMELINE_CATEGORY_LABELS[TIMELINE_CATEGORY_REPAYMENT],
                "headline": f"Repayment {payment['payment_amount']}",
                "collections_status": None,
                "context_notes": payment["repayment_notes"] or "",
                "is_critical": False,
                "recovery_badge": "Repayment",
                "batch_id": None,
            }
        )

    events.sort(key=lambda e: (e["created_at"] or "", e["source"]), reverse=True)

    grouped: dict[str, list[dict]] = {}
    for event in events:
        grouped.setdefault(event["category"], []).append(event)

    actor_counts: dict[str, int] = {}
    for event in events:
        actor = event["actor"] or "unknown"
        actor_counts[actor] = actor_counts.get(actor, 0) + 1

    operator_summary = [
        {"actor": actor, "event_count": count}
        for actor, count in sorted(actor_counts.items(), key=lambda x: (-x[1], x[0]))[:8]
    ]

    category_order = [
        TIMELINE_CATEGORY_ESCALATION,
        TIMELINE_CATEGORY_LEGAL,
        TIMELINE_CATEGORY_WRITEOFF,
        TIMELINE_CATEGORY_REPAYMENT,
        TIMELINE_CATEGORY_PROMISE,
        TIMELINE_CATEGORY_CONTACT,
        TIMELINE_CATEGORY_GENERAL,
    ]
    for key in grouped:
        if key not in category_order:
            category_order.append(key)

    return {
        "events": events,
        "grouped": grouped,
        "category_order": [c for c in category_order if c in grouped],
        "operator_summary": operator_summary,
        "total_events": len(events),
    }
