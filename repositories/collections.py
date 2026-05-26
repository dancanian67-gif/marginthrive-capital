"""Collections persistence and queue queries (Phase F1)."""

import sqlite3

from constants.collections import (
    COLLECTIONS_HISTORY_LIMIT,
    COLLECTIONS_PAGE_SIZE,
    COLLECTIONS_QUEUE_LIMIT,
    COLLECTIONS_STATUSES,
    DELINQUENCY_BUCKET_LABELS,
    DEFAULT_COLLECTIONS_PRIORITY,
    DEFAULT_COLLECTIONS_RISK_LEVEL,
    DEFAULT_COLLECTIONS_STATUS,
)
from constants.loans import ACTIVE_LOAN_LIFECYCLE_STATUSES, SERVICING_LOAN_LIFECYCLE_STATUSES
from constants.portfolio import COLLECTIONS_RISK_LEVELS as PORTFOLIO_COLLECTIONS_RISK

_ACTIVE_IN = ", ".join(f"'{s}'" for s in ACTIVE_LOAN_LIFECYCLE_STATUSES)
_SERVICING_IN = ", ".join(f"'{s}'" for s in SERVICING_LOAN_LIFECYCLE_STATUSES)
_COLLECTIONS_RISK_IN = ", ".join(f"'{s}'" for s in PORTFOLIO_COLLECTIONS_RISK)


def _delinquency_days_sql(alias: str = "a") -> str:
    return f"""
        CASE
            WHEN {alias}.due_date IS NOT NULL AND TRIM({alias}.due_date) != ''
                 AND COALESCE({alias}.outstanding_balance, 0) > 0
            THEN MAX(
                0,
                CAST(julianday('now') - julianday(date({alias}.due_date)) AS INTEGER)
            )
            ELSE 0
        END
    """


def _delinquency_bucket_sql(alias: str = "a") -> str:
    days = _delinquency_days_sql(alias)
    return f"""
        CASE
            WHEN {alias}.loan_lifecycle_status IN ('completed', 'written_off', 'not_issued') THEN 'current'
            WHEN {alias}.due_date IS NULL OR TRIM({alias}.due_date) = '' THEN 'no_due_date'
            WHEN ({days}) <= 0 THEN 'current'
            WHEN ({days}) BETWEEN 1 AND 30 THEN '1_30_days'
            WHEN ({days}) BETWEEN 31 AND 60 THEN '31_60_days'
            WHEN ({days}) BETWEEN 61 AND 90 THEN '61_90_days'
            ELSE '90_plus_days'
        END
    """


def collections_queue_predicate(alias: str = "a") -> str:
    days = _delinquency_days_sql(alias)
    return f"""
        (
            {alias}.loan_lifecycle_status IN ('overdue', 'defaulted')
            OR {alias}.repayment_risk_level IN ({_COLLECTIONS_RISK_IN})
            OR (
                {alias}.loan_lifecycle_status IN ('active', 'repaying')
                AND {alias}.due_date IS NOT NULL AND TRIM({alias}.due_date) != ''
                AND date({alias}.due_date) < date('now')
                AND COALESCE({alias}.outstanding_balance, 0) > 0
            )
            OR {alias}.collections_status NOT IN ('not_in_collections', 'resolved')
        )
        AND {alias}.loan_lifecycle_status IN ({_SERVICING_IN})
    """


def migrate_collections_columns(cursor) -> None:
    cursor.execute(
        """
        UPDATE applications
        SET collections_status = ?
        WHERE collections_status IS NULL OR collections_status = ''
        """,
        (DEFAULT_COLLECTIONS_STATUS,),
    )
    cursor.execute(
        """
        UPDATE applications
        SET collections_priority = ?
        WHERE collections_priority IS NULL OR collections_priority = ''
        """,
        (DEFAULT_COLLECTIONS_PRIORITY,),
    )
    cursor.execute(
        """
        UPDATE applications
        SET collections_risk_level = ?
        WHERE collections_risk_level IS NULL OR collections_risk_level = ''
        """,
        (DEFAULT_COLLECTIONS_RISK_LEVEL,),
    )


def init_collections_history_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS collections_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            batch_id TEXT NOT NULL,
            collections_status TEXT NOT NULL,
            collections_priority TEXT NOT NULL,
            collections_assigned_to TEXT NOT NULL DEFAULT '',
            collections_last_contact_at TEXT,
            collections_next_follow_up TEXT,
            collections_notes_summary TEXT NOT NULL DEFAULT '',
            collections_risk_level TEXT NOT NULL,
            action_type TEXT NOT NULL DEFAULT 'collections_update',
            actor TEXT NOT NULL,
            context_notes TEXT NOT NULL DEFAULT '',
            is_critical INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_collections_history_application
        ON collections_history (application_id, created_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_applications_collections_status
        ON applications (collections_status)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_applications_collections_assigned
        ON applications (collections_assigned_to)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_applications_collections_follow_up
        ON applications (collections_next_follow_up)
        """
    )


def insert_collections_history_record(
    cursor,
    *,
    application_id: int,
    batch_id: str,
    snapshot: dict,
    actor: str,
    action_type: str,
    context_notes: str,
    is_critical: int,
) -> None:
    cursor.execute(
        """
        INSERT INTO collections_history (
            application_id,
            batch_id,
            collections_status,
            collections_priority,
            collections_assigned_to,
            collections_last_contact_at,
            collections_next_follow_up,
            collections_notes_summary,
            collections_risk_level,
            action_type,
            actor,
            context_notes,
            is_critical
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            application_id,
            batch_id,
            snapshot["collections_status"],
            snapshot["collections_priority"],
            snapshot["collections_assigned_to"],
            snapshot["collections_last_contact_at"],
            snapshot["collections_next_follow_up"],
            snapshot["collections_notes_summary"],
            snapshot["collections_risk_level"],
            action_type,
            actor,
            context_notes,
            is_critical,
        ),
    )


def fetch_collections_history_rows(
    cursor,
    application_id: int,
    limit: int = COLLECTIONS_HISTORY_LIMIT,
) -> list[sqlite3.Row]:
    cursor.execute(
        """
        SELECT *
        FROM collections_history
        WHERE application_id = ?
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT ?
        """,
        (application_id, limit),
    )
    return cursor.fetchall()


def fetch_collections_queue_kpis(cursor) -> dict:
    predicate = collections_queue_predicate("a")
    cursor.execute(
        f"""
        SELECT
            COUNT(*) AS queue_total,
            SUM(CASE WHEN collections_priority = 'urgent' THEN 1 ELSE 0 END) AS urgent_count,
            SUM(CASE WHEN collections_status = 'legal_escalation' THEN 1 ELSE 0 END) AS legal_count,
            SUM(CASE
                WHEN collections_next_follow_up IS NOT NULL
                 AND TRIM(collections_next_follow_up) != ''
                 AND date(collections_next_follow_up) <= date('now')
                THEN 1 ELSE 0 END) AS follow_up_due_count,
            SUM(COALESCE(outstanding_balance, 0)) AS total_exposure
        FROM applications a
        WHERE {predicate}
        """
    )
    row = cursor.fetchone()
    return {
        "queue_total": row["queue_total"] or 0,
        "urgent_count": row["urgent_count"] or 0,
        "legal_count": row["legal_count"] or 0,
        "follow_up_due_count": row["follow_up_due_count"] or 0,
        "total_exposure": round(row["total_exposure"] or 0, 2),
    }


def build_collections_where(filters: dict) -> tuple[str, list]:
    clauses = [collections_queue_predicate("a")]
    params: list = []

    status = (filters.get("collections_status") or "").strip()
    if status:
        clauses.append("a.collections_status = ?")
        params.append(status)

    priority = (filters.get("collections_priority") or "").strip()
    if priority:
        clauses.append("a.collections_priority = ?")
        params.append(priority)

    assigned = (filters.get("collections_assigned_to") or "").strip()
    if assigned:
        clauses.append("a.collections_assigned_to LIKE ?")
        params.append(f"%{assigned}%")

    risk = (filters.get("collections_risk_level") or "").strip()
    if risk:
        clauses.append("a.collections_risk_level = ?")
        params.append(risk)

    bucket = (filters.get("delinquency_bucket") or "").strip()
    if bucket:
        clauses.append(f"{_delinquency_bucket_sql('a')} = ?")
        params.append(bucket)

    search = (filters.get("q") or "").strip()
    if search:
        clauses.append(
            "(a.business_name LIKE ? OR a.owner_name LIKE ? OR a.loan_account_number LIKE ?)"
        )
        like = f"%{search}%"
        params.extend([like, like, like])

    promise_filter = (filters.get("promise_filter") or "").strip()
    if promise_filter:
        from repositories.promises import promise_queue_filter_sql

        fragment = promise_queue_filter_sql(promise_filter, "a")
        if fragment:
            sql_part, extra_params = fragment
            clauses.append(sql_part.strip())
            params.extend(extra_params)

    where_sql = " WHERE " + " AND ".join(clauses) if clauses else ""
    return where_sql, params


def fetch_collections_queue(
    cursor,
    filters: dict,
    *,
    limit: int = COLLECTIONS_QUEUE_LIMIT,
    offset: int = 0,
) -> list[sqlite3.Row]:
    where_sql, params = build_collections_where(filters)
    days_sql = _delinquency_days_sql("a")
    bucket_sql = _delinquency_bucket_sql("a")
    cursor.execute(
        f"""
        SELECT
            a.*,
            {days_sql} AS days_overdue,
            {bucket_sql} AS delinquency_bucket
        FROM applications a
        {where_sql}
        ORDER BY
            CASE a.collections_priority
                WHEN 'urgent' THEN 4
                WHEN 'high' THEN 3
                WHEN 'normal' THEN 2
                ELSE 1
            END DESC,
            {days_sql} DESC,
            COALESCE(a.outstanding_balance, 0) DESC,
            a.id DESC
        LIMIT ? OFFSET ?
        """,
        (*params, limit, offset),
    )
    return cursor.fetchall()


def count_collections_queue(cursor, filters: dict) -> int:
    where_sql, params = build_collections_where(filters)
    cursor.execute(
        f"SELECT COUNT(*) FROM applications a {where_sql}",
        params,
    )
    return cursor.fetchone()[0] or 0


def fetch_collections_delinquency_distribution(cursor) -> list[dict]:
    predicate = collections_queue_predicate("a")
    bucket_sql = _delinquency_bucket_sql("a")
    cursor.execute(
        f"""
        SELECT {bucket_sql} AS label, COUNT(*) AS count,
               SUM(COALESCE(outstanding_balance, 0)) AS exposure
        FROM applications a
        WHERE {predicate}
        GROUP BY label
        ORDER BY count DESC
        """
    )
    return [
        {
            "label": DELINQUENCY_BUCKET_LABELS.get(row["label"], row["label"]),
            "bucket": row["label"],
            "count": row["count"],
            "exposure": round(row["exposure"] or 0, 2),
        }
        for row in cursor.fetchall()
    ]


def fetch_collections_officer_workload(cursor) -> list[dict]:
    predicate = collections_queue_predicate("a")
    cursor.execute(
        f"""
        SELECT
            CASE
                WHEN collections_assigned_to IS NULL OR TRIM(collections_assigned_to) = ''
                THEN 'Unassigned'
                ELSE collections_assigned_to
            END AS officer_label,
            COUNT(*) AS case_count,
            SUM(COALESCE(outstanding_balance, 0)) AS exposure,
            SUM(CASE WHEN collections_priority IN ('high', 'urgent') THEN 1 ELSE 0 END) AS high_priority_cases
        FROM applications a
        WHERE {predicate}
        GROUP BY officer_label
        ORDER BY exposure DESC, case_count DESC
        LIMIT 12
        """
    )
    return [
        {
            "officer": row["officer_label"],
            "case_count": row["case_count"],
            "exposure": round(row["exposure"] or 0, 2),
            "high_priority_cases": row["high_priority_cases"] or 0,
        }
        for row in cursor.fetchall()
    ]


def fetch_collections_activity_for_export(
    cursor,
    range_clause: str,
    range_params: list,
    limit: int,
) -> list[dict]:
    cursor.execute(
        f"""
        SELECT
            ch.id,
            ch.application_id,
            a.business_name,
            a.loan_account_number,
            ch.collections_status,
            ch.collections_priority,
            ch.collections_assigned_to,
            ch.collections_risk_level,
            ch.action_type,
            ch.actor,
            ch.context_notes,
            ch.created_at
        FROM collections_history ch
        INNER JOIN applications a ON a.id = ch.application_id
        WHERE ch.created_at IS NOT NULL AND ch.created_at != ''{range_clause}
        ORDER BY datetime(ch.created_at) DESC, ch.id DESC
        LIMIT ?
        """,
        (*range_params, limit),
    )
    return [dict(row) for row in cursor.fetchall()]


def iter_collections_queue_for_export(cursor, filters: dict, *, batch_size: int = 500):
    offset = 0
    days_sql = _delinquency_days_sql("a")
    bucket_sql = _delinquency_bucket_sql("a")
    while True:
        where_sql, params = build_collections_where(filters)
        cursor.execute(
            f"""
            SELECT
                a.id,
                a.business_name,
                a.owner_name,
                a.loan_account_number,
                a.loan_lifecycle_status,
                a.outstanding_balance,
                a.due_date,
                {days_sql} AS days_overdue,
                {bucket_sql} AS delinquency_bucket,
                a.repayment_risk_level,
                a.collections_status,
                a.collections_priority,
                a.collections_assigned_to,
                a.collections_risk_level,
                a.collections_next_follow_up,
                a.collections_last_contact_at
            FROM applications a
            {where_sql}
            ORDER BY {days_sql} DESC, a.id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, batch_size, offset),
        )
        rows = cursor.fetchall()
        if not rows:
            break
        for row in rows:
            item = dict(row)
            item["delinquency_bucket"] = DELINQUENCY_BUCKET_LABELS.get(
                item["delinquency_bucket"],
                item["delinquency_bucket"],
            )
            yield item
        if len(rows) < batch_size:
            break
        offset += batch_size


def fetch_invalid_collections_statuses(cursor) -> list[str]:
    placeholders = ", ".join("?" * len(COLLECTIONS_STATUSES))

    cursor.execute(
        f"""
        SELECT DISTINCT collections_status FROM applications
        WHERE collections_status IS NOT NULL
          AND collections_status != ''
          AND collections_status NOT IN ({placeholders})
        LIMIT 10
        """,
        tuple(COLLECTIONS_STATUSES),
    )
    return [row[0] for row in cursor.fetchall()]


def count_orphaned_collections_history(cursor) -> int:
    cursor.execute(
        """
        SELECT COUNT(*) FROM collections_history ch
        WHERE NOT EXISTS (SELECT 1 FROM applications a WHERE a.id = ch.application_id)
        """
    )
    return cursor.fetchone()[0] or 0
