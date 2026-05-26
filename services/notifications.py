"""Operator notification center (Phase G1)."""

from __future__ import annotations

from constants.events import (
    EVENT_CATEGORY_LABELS,
    EVENT_SEVERITY_LABELS,
    NOTIFICATION_FILTER_LABELS,
    NOTIFICATION_FILTERS,
    NOTIFICATION_PAGE_SIZE,
)
from repositories.notifications import (
    acknowledge_notification,
    count_notifications_filtered,
    fetch_notification_summary,
    fetch_notifications_page,
)
from services.notification_alerts import build_operational_alert_banners


def parse_notification_filters(args) -> dict:
    raw = (args.get("filter") or "").strip()
    if raw not in NOTIFICATION_FILTERS:
        raw = ""
    page = max(1, int(args.get("page") or 1))
    return {"filter": raw, "page": page}


def build_notifications_page(cursor, operator_id: int, filters: dict) -> dict:
    filter_key = filters["filter"]
    page = filters["page"]
    offset = (page - 1) * NOTIFICATION_PAGE_SIZE
    total = count_notifications_filtered(cursor, operator_id, filter_key=filter_key)
    rows = fetch_notifications_page(
        cursor,
        operator_id,
        filter_key=filter_key,
        limit=NOTIFICATION_PAGE_SIZE,
        offset=offset,
    )
    items = []
    for row in rows:
        items.append(
            {
                "id": row["id"],
                "event_id": row["event_id"],
                "category": row["event_category"],
                "category_label": EVENT_CATEGORY_LABELS.get(row["event_category"], row["event_category"]),
                "severity": row["severity"],
                "severity_label": EVENT_SEVERITY_LABELS.get(row["severity"], row["severity"]),
                "title": row["title"],
                "message": row["message"],
                "application_id": row["application_id"],
                "business_name": row["application_business_name"] or "",
                "governance_tag": row["governance_tag"] or "",
                "is_acknowledged": bool(row["is_acknowledged"]),
                "acknowledged_at": row["acknowledged_at"] or "",
                "acknowledged_by": row["acknowledged_by"] or "",
                "created_at": row["created_at"],
            }
        )
    page_count = max(1, (total + NOTIFICATION_PAGE_SIZE - 1) // NOTIFICATION_PAGE_SIZE)
    summary = fetch_notification_summary(cursor, operator_id)
    alerts = build_operational_alert_banners(cursor)
    return {
        "notifications": items,
        "summary": summary,
        "operational_alerts": alerts,
        "filter": filter_key,
        "filter_label": NOTIFICATION_FILTER_LABELS.get(filter_key, NOTIFICATION_FILTER_LABELS[""]),
        "filters": NOTIFICATION_FILTERS,
        "filter_labels": NOTIFICATION_FILTER_LABELS,
        "page": page,
        "page_count": page_count,
        "total": total,
        "page_size": NOTIFICATION_PAGE_SIZE,
        "has_prev": page > 1,
        "has_next": page < page_count,
    }


def persist_notification_acknowledgement(
    notification_id: int,
    operator_id: int,
    *,
    acknowledged_by: str,
) -> bool:
    from repositories.database import get_db_connection
    from utils.db_write import commit_connection

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        ok = acknowledge_notification(
            cursor,
            notification_id,
            operator_id,
            acknowledged_by=acknowledged_by,
        )
        if ok:
            commit_connection(conn, operation_name="notification_ack_commit")
        else:
            conn.rollback()
        return ok
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
