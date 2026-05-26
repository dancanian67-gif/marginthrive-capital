"""Operational events and operator notifications persistence (Phase G1)."""

from __future__ import annotations

import sqlite3

from constants.events import NOTIFICATION_PAGE_SIZE


def init_operational_notifications_tables(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS operational_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_category TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'info',
            title TEXT NOT NULL,
            message TEXT NOT NULL DEFAULT '',
            application_id INTEGER,
            actor TEXT NOT NULL,
            operator_id INTEGER,
            governance_tag TEXT,
            source_type TEXT,
            source_id TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS operator_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            target_operator_id INTEGER,
            event_category TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'info',
            title TEXT NOT NULL,
            message TEXT NOT NULL DEFAULT '',
            application_id INTEGER,
            governance_tag TEXT,
            is_acknowledged INTEGER NOT NULL DEFAULT 0,
            acknowledged_at TEXT,
            acknowledged_by TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_operational_events_category_created
        ON operational_events (event_category, created_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_operational_events_application
        ON operational_events (application_id, created_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_operator_notifications_target_unread
        ON operator_notifications (target_operator_id, is_acknowledged, severity, created_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_operator_notifications_application
        ON operator_notifications (application_id, created_at DESC)
        """
    )


def insert_operational_event(
    cursor,
    *,
    event_category: str,
    severity: str,
    title: str,
    message: str,
    application_id: int | None,
    actor: str,
    operator_id: int | None,
    governance_tag: str | None,
    source_type: str | None,
    source_id: str | None,
) -> int:
    cursor.execute(
        """
        INSERT INTO operational_events (
            event_category,
            severity,
            title,
            message,
            application_id,
            actor,
            operator_id,
            governance_tag,
            source_type,
            source_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_category,
            severity,
            title,
            message[:2000],
            application_id,
            actor,
            operator_id,
            governance_tag,
            source_type,
            source_id,
        ),
    )
    return int(cursor.lastrowid)


def insert_operator_notification(
    cursor,
    *,
    event_id: int,
    target_operator_id: int | None,
    event_category: str,
    severity: str,
    title: str,
    message: str,
    application_id: int | None,
    governance_tag: str | None,
) -> int:
    cursor.execute(
        """
        INSERT INTO operator_notifications (
            event_id,
            target_operator_id,
            event_category,
            severity,
            title,
            message,
            application_id,
            governance_tag
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            target_operator_id,
            event_category,
            severity,
            title,
            message[:2000],
            application_id,
            governance_tag,
        ),
    )
    return int(cursor.lastrowid)


def resolve_operator_id_by_username(cursor, username: str | None) -> int | None:
    raw = (username or "").strip()
    if not raw:
        return None
    cursor.execute(
        """
        SELECT id FROM operators
        WHERE active = 1 AND LOWER(username) = LOWER(?)
        LIMIT 1
        """,
        (raw,),
    )
    row = cursor.fetchone()
    return int(row[0]) if row else None


def notification_visible_sql(operator_id: int) -> tuple[str, list]:
    """Notifications broadcast (NULL target) or scoped to this operator."""
    return (
        "(n.target_operator_id IS NULL OR n.target_operator_id = ?)",
        [operator_id],
    )


def count_unread_notifications(cursor, operator_id: int) -> int:
    vis_sql, vis_params = notification_visible_sql(operator_id)
    cursor.execute(
        f"""
        SELECT COUNT(*) FROM operator_notifications n
        WHERE {vis_sql} AND n.is_acknowledged = 0
        """,
        vis_params,
    )
    return cursor.fetchone()[0] or 0


def fetch_notifications_page(
    cursor,
    operator_id: int,
    *,
    filter_key: str = "",
    limit: int = NOTIFICATION_PAGE_SIZE,
    offset: int = 0,
) -> list[sqlite3.Row]:
    vis_sql, vis_params = notification_visible_sql(operator_id)
    clauses = [vis_sql]
    params: list = list(vis_params)

    if filter_key == "unread":
        clauses.append("n.is_acknowledged = 0")
    elif filter_key == "critical":
        clauses.append("n.severity = 'critical'")
    elif filter_key == "governance":
        clauses.append("n.governance_tag IS NOT NULL AND n.governance_tag != ''")

    where = " AND ".join(clauses)
    cursor.execute(
        f"""
        SELECT
            n.*,
            a.business_name AS application_business_name
        FROM operator_notifications n
        LEFT JOIN applications a ON a.id = n.application_id
        WHERE {where}
        ORDER BY n.is_acknowledged ASC, n.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (*params, limit, offset),
    )
    return cursor.fetchall()


def count_notifications_filtered(cursor, operator_id: int, *, filter_key: str = "") -> int:
    vis_sql, vis_params = notification_visible_sql(operator_id)
    clauses = [vis_sql]
    params: list = list(vis_params)
    if filter_key == "unread":
        clauses.append("n.is_acknowledged = 0")
    elif filter_key == "critical":
        clauses.append("n.severity = 'critical'")
    elif filter_key == "governance":
        clauses.append("n.governance_tag IS NOT NULL AND n.governance_tag != ''")
    cursor.execute(
        f"SELECT COUNT(*) FROM operator_notifications n WHERE {' AND '.join(clauses)}",
        params,
    )
    return cursor.fetchone()[0] or 0


def acknowledge_notification(
    cursor,
    notification_id: int,
    operator_id: int,
    *,
    acknowledged_by: str,
) -> bool:
    vis_sql, vis_params = notification_visible_sql(operator_id)
    vis_sql = vis_sql.replace("n.", "")
    cursor.execute(
        f"""
        UPDATE operator_notifications
        SET is_acknowledged = 1,
            acknowledged_at = datetime('now'),
            acknowledged_by = ?
        WHERE id = ?
          AND is_acknowledged = 0
          AND {vis_sql}
        """,
        (acknowledged_by, notification_id, *vis_params),
    )
    return cursor.rowcount > 0


def fetch_notification_summary(cursor, operator_id: int, *, limit: int = 8) -> dict:
    vis_sql, vis_params = notification_visible_sql(operator_id)
    cursor.execute(
        f"""
        SELECT COUNT(*) FROM operator_notifications n
        WHERE {vis_sql}
        """,
        vis_params,
    )
    total = cursor.fetchone()[0] or 0
    cursor.execute(
        f"""
        SELECT COUNT(*) FROM operator_notifications n
        WHERE {vis_sql} AND n.is_acknowledged = 0
        """,
        vis_params,
    )
    unread = cursor.fetchone()[0] or 0
    cursor.execute(
        f"""
        SELECT COUNT(*) FROM operator_notifications n
        WHERE {vis_sql} AND n.is_acknowledged = 0 AND n.severity = 'critical'
        """,
        vis_params,
    )
    unread_critical = cursor.fetchone()[0] or 0
    cursor.execute(
        f"""
        SELECT n.severity, COUNT(*) AS c
        FROM operator_notifications n
        WHERE {vis_sql} AND n.is_acknowledged = 0
        GROUP BY n.severity
        """,
        vis_params,
    )
    by_severity = {row["severity"]: row["c"] for row in cursor.fetchall()}
    cursor.execute(
        f"""
        SELECT n.id, n.title, n.severity, n.created_at, n.application_id
        FROM operator_notifications n
        WHERE {vis_sql} AND n.is_acknowledged = 0
        ORDER BY
            CASE n.severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
            n.created_at DESC
        LIMIT ?
        """,
        (*vis_params, limit),
    )
    recent_unread = [dict(row) for row in cursor.fetchall()]
    return {
        "total": total,
        "unread": unread,
        "unread_critical": unread_critical,
        "by_severity": by_severity,
        "recent_unread": recent_unread,
    }


def has_recent_notification(
    cursor,
    *,
    event_category: str,
    application_id: int | None,
    days: int = 7,
) -> bool:
    clauses = ["n.event_category = ?", "n.created_at >= datetime('now', ?)"]
    params: list = [event_category, f"-{days} days"]
    if application_id is not None:
        clauses.append("n.application_id = ?")
        params.append(application_id)
    else:
        clauses.append("n.application_id IS NULL")
    cursor.execute(
        f"SELECT 1 FROM operator_notifications n WHERE {' AND '.join(clauses)} LIMIT 1",
        params,
    )
    return cursor.fetchone() is not None


def count_orphaned_notifications(cursor) -> int:
    cursor.execute(
        """
        SELECT COUNT(*) FROM operator_notifications n
        WHERE NOT EXISTS (SELECT 1 FROM operational_events e WHERE e.id = n.event_id)
        """
    )
    return cursor.fetchone()[0] or 0


def count_invalid_acknowledgement_states(cursor) -> int:
    cursor.execute(
        """
        SELECT COUNT(*) FROM operator_notifications
        WHERE is_acknowledged = 1
          AND (acknowledged_at IS NULL OR acknowledged_at = '' OR acknowledged_by IS NULL OR acknowledged_by = '')
        """
    )
    return cursor.fetchone()[0] or 0


def count_unresolved_critical_notifications(cursor) -> int:
    cursor.execute(
        """
        SELECT COUNT(*) FROM operator_notifications
        WHERE severity = 'critical' AND is_acknowledged = 0
        """
    )
    return cursor.fetchone()[0] or 0


def count_excessive_notification_backlog(cursor, *, threshold: int = 500) -> int:
    cursor.execute(
        """
        SELECT COUNT(*) FROM operator_notifications
        WHERE is_acknowledged = 0
        """
    )
    total = cursor.fetchone()[0] or 0
    return total if total >= threshold else 0


def fetch_notification_analytics_metrics(cursor, range_key: str) -> dict:
    from utils.time_range import analytics_datetime_clause

    range_clause, range_params = analytics_datetime_clause(range_key, "created_at")
    period_where = f"WHERE 1=1{range_clause}"
    cursor.execute(
        f"""
        SELECT COUNT(*) FROM operator_notifications
        {period_where}
        """,
        range_params,
    )
    total_period = cursor.fetchone()[0] or 0
    cursor.execute(
        f"""
        SELECT COUNT(*) FROM operator_notifications
        {period_where} AND is_acknowledged = 0
        """,
        range_params,
    )
    unresolved_period = cursor.fetchone()[0] or 0
    cursor.execute(
        f"""
        SELECT severity, COUNT(*) AS c
        FROM operator_notifications
        {period_where}
        GROUP BY severity
        """,
        range_params,
    )
    severity_dist = {row["severity"]: row["c"] for row in cursor.fetchall()}
    cursor.execute(
        f"""
        SELECT COUNT(*) FROM operator_notifications
        {period_where} AND is_acknowledged = 1
        """,
        range_params,
    )
    acknowledged = cursor.fetchone()[0] or 0
    ack_rate = round((acknowledged / total_period) * 100, 1) if total_period else 0.0
    event_period_where = f"WHERE 1=1{range_clause}"
    cursor.execute(
        f"""
        SELECT AVG(
            CAST(
                (julianday(COALESCE(acknowledged_at, datetime('now')) - julianday(created_at)) * 24)
                AS REAL
            )
        )
        FROM operator_notifications
        {period_where}
          AND is_acknowledged = 1
          AND acknowledged_at IS NOT NULL
        """,
        range_params,
    )
    avg_ack_hours = round(cursor.fetchone()[0] or 0.0, 1)
    cursor.execute(
        f"""
        SELECT COUNT(*) FROM operator_notifications
        {period_where}
          AND governance_tag IS NOT NULL AND governance_tag != ''
        """,
        range_params,
    )
    governance_alerts = cursor.fetchone()[0] or 0
    cursor.execute(
        f"""
        SELECT COUNT(*) FROM operator_notifications
        WHERE is_acknowledged = 0
          AND severity = 'critical'
          AND created_at < datetime('now', '-3 days')
        """,
    )
    aging_critical = cursor.fetchone()[0] or 0
    cursor.execute(
        f"""
        SELECT event_category, COUNT(*) AS c
        FROM operational_events
        {event_period_where}
        GROUP BY event_category
        ORDER BY c DESC
        LIMIT 6
        """,
        range_params,
    )
    category_trend = [{"category": row["event_category"], "count": row["c"]} for row in cursor.fetchall()]
    return {
        "total_period": total_period,
        "unresolved_period": unresolved_period,
        "severity_distribution": severity_dist,
        "acknowledgement_rate_pct": ack_rate,
        "avg_acknowledgement_hours": avg_ack_hours,
        "governance_alerts_period": governance_alerts,
        "aging_critical_unresolved": aging_critical,
        "category_trend": category_trend,
    }


def iter_operational_alerts_export(cursor, *, batch_size: int = 500):
    cursor.execute(
        """
        SELECT
            n.id,
            n.event_category,
            n.severity,
            n.title,
            n.message,
            n.application_id,
            a.business_name,
            n.governance_tag,
            n.is_acknowledged,
            n.acknowledged_at,
            n.acknowledged_by,
            n.created_at
        FROM operator_notifications n
        LEFT JOIN applications a ON a.id = n.application_id
        ORDER BY n.created_at DESC
        """
    )
    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
        for row in rows:
            yield row


def fetch_unresolved_notifications_export(cursor, limit: int) -> list:
    cursor.execute(
        """
        SELECT
            n.id,
            n.event_category,
            n.severity,
            n.title,
            n.application_id,
            a.business_name,
            n.governance_tag,
            n.created_at
        FROM operator_notifications n
        LEFT JOIN applications a ON a.id = n.application_id
        WHERE n.is_acknowledged = 0
        ORDER BY
            CASE n.severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
            n.created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return cursor.fetchall()


def fetch_governance_alerts_export(cursor, limit: int) -> list:
    cursor.execute(
        """
        SELECT
            n.id,
            n.event_category,
            n.severity,
            n.title,
            n.governance_tag,
            n.application_id,
            a.business_name,
            n.is_acknowledged,
            n.created_at
        FROM operator_notifications n
        LEFT JOIN applications a ON a.id = n.application_id
        WHERE n.governance_tag IS NOT NULL AND n.governance_tag != ''
        ORDER BY n.created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return cursor.fetchall()


def fetch_operator_acknowledgement_metrics_export(cursor) -> list:
    cursor.execute(
        """
        SELECT
            COALESCE(o.username, 'broadcast') AS operator_scope,
            COUNT(*) AS total_notifications,
            SUM(CASE WHEN n.is_acknowledged = 1 THEN 1 ELSE 0 END) AS acknowledged,
            SUM(CASE WHEN n.is_acknowledged = 0 THEN 1 ELSE 0 END) AS unresolved,
            SUM(CASE WHEN n.severity = 'critical' AND n.is_acknowledged = 0 THEN 1 ELSE 0 END) AS critical_unresolved
        FROM operator_notifications n
        LEFT JOIN operators o ON o.id = n.target_operator_id
        GROUP BY n.target_operator_id
        ORDER BY unresolved DESC, total_notifications DESC
        """
    )
    rows = cursor.fetchall()
    result = []
    for row in rows:
        total = row["total_notifications"] or 0
        ack = row["acknowledged"] or 0
        rate = round((ack / total) * 100, 1) if total else 0.0
        result.append(
            {
                "operator_scope": row["operator_scope"],
                "total_notifications": total,
                "acknowledged": ack,
                "unresolved": row["unresolved"] or 0,
                "critical_unresolved": row["critical_unresolved"] or 0,
                "acknowledgement_rate_pct": rate,
            }
        )
    return result


def fetch_critical_event_summary_export(cursor, limit: int) -> list:
    cursor.execute(
        """
        SELECT
            e.id,
            e.event_category,
            e.severity,
            e.title,
            e.application_id,
            a.business_name,
            e.actor,
            e.governance_tag,
            e.created_at
        FROM operational_events e
        LEFT JOIN applications a ON a.id = e.application_id
        WHERE e.severity = 'critical'
        ORDER BY e.created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return cursor.fetchall()
