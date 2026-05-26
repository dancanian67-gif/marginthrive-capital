"""Recovery promise persistence (Phase F3)."""

import sqlite3

from constants.promises import (
    DEFAULT_PROMISE_STATUS,
    PROMISE_HISTORY_LIMIT,
    PROMISE_STATUSES,
    TERMINAL_PROMISE_STATUSES,
)


def init_recovery_promises_tables(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS recovery_promises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            batch_id TEXT NOT NULL,
            promise_amount REAL NOT NULL,
            promise_date TEXT NOT NULL,
            promise_status TEXT NOT NULL DEFAULT 'active',
            commitment_notes TEXT NOT NULL DEFAULT '',
            created_by TEXT NOT NULL,
            fulfilled_at TEXT,
            broken_at TEXT,
            cancelled_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS recovery_promise_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            promise_id INTEGER NOT NULL,
            application_id INTEGER NOT NULL,
            batch_id TEXT NOT NULL,
            promise_amount REAL NOT NULL,
            promise_date TEXT NOT NULL,
            promise_status TEXT NOT NULL,
            commitment_notes TEXT NOT NULL DEFAULT '',
            action_type TEXT NOT NULL DEFAULT 'promise_update',
            actor TEXT NOT NULL,
            context_notes TEXT NOT NULL DEFAULT '',
            is_critical INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_recovery_promises_application
        ON recovery_promises (application_id, promise_status, promise_date)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_recovery_promises_status_date
        ON recovery_promises (promise_status, promise_date)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_recovery_promise_history_promise
        ON recovery_promise_history (promise_id, created_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_recovery_promise_history_application
        ON recovery_promise_history (application_id, created_at DESC)
        """
    )


def insert_promise_history_record(
    cursor,
    *,
    promise_id: int,
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
        INSERT INTO recovery_promise_history (
            promise_id,
            application_id,
            batch_id,
            promise_amount,
            promise_date,
            promise_status,
            commitment_notes,
            action_type,
            actor,
            context_notes,
            is_critical
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            promise_id,
            application_id,
            batch_id,
            snapshot["promise_amount"],
            snapshot["promise_date"],
            snapshot["promise_status"],
            snapshot["commitment_notes"],
            action_type,
            actor,
            context_notes,
            is_critical,
        ),
    )


def fetch_active_promise(cursor, application_id: int) -> sqlite3.Row | None:
    cursor.execute(
        """
        SELECT * FROM recovery_promises
        WHERE application_id = ? AND promise_status = 'active'
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT 1
        """,
        (application_id,),
    )
    return cursor.fetchone()


def fetch_promise_by_id(cursor, promise_id: int) -> sqlite3.Row | None:
    cursor.execute("SELECT * FROM recovery_promises WHERE id = ?", (promise_id,))
    return cursor.fetchone()


def fetch_promise_history_rows(
    cursor,
    application_id: int,
    *,
    promise_id: int | None = None,
    limit: int = PROMISE_HISTORY_LIMIT,
) -> list[sqlite3.Row]:
    if promise_id is not None:
        cursor.execute(
            """
            SELECT * FROM recovery_promise_history
            WHERE promise_id = ?
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT ?
            """,
            (promise_id, limit),
        )
    else:
        cursor.execute(
            """
            SELECT * FROM recovery_promise_history
            WHERE application_id = ?
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT ?
            """,
            (application_id, limit),
        )
    return cursor.fetchall()


def fetch_all_promises_for_application(cursor, application_id: int) -> list[sqlite3.Row]:
    cursor.execute(
        """
        SELECT * FROM recovery_promises
        WHERE application_id = ?
        ORDER BY datetime(created_at) DESC, id DESC
        """,
        (application_id,),
    )
    return cursor.fetchall()


def count_active_promises_by_application(cursor, application_ids: list[int]) -> dict[int, int]:
    if not application_ids:
        return {}
    placeholders = ", ".join("?" * len(application_ids))
    cursor.execute(
        f"""
        SELECT application_id, COUNT(*) AS cnt
        FROM recovery_promises
        WHERE application_id IN ({placeholders}) AND promise_status = 'active'
        GROUP BY application_id
        """,
        application_ids,
    )
    return {row["application_id"]: row["cnt"] for row in cursor.fetchall()}


def fetch_promise_summaries_for_applications(cursor, application_ids: list[int]) -> dict[int, dict]:
    if not application_ids:
        return {}
    result: dict[int, dict] = {}
    for app_id in application_ids:
        result[app_id] = fetch_promise_summary_for_application(cursor, app_id)
    return result


def fetch_promise_summary_for_application(cursor, application_id: int) -> dict:
    active = fetch_active_promise(cursor, application_id)
    cursor.execute(
        """
        SELECT COUNT(*) FROM recovery_promises
        WHERE application_id = ? AND promise_status = 'broken'
        """,
        (application_id,),
    )
    broken_count = cursor.fetchone()[0] or 0
    cursor.execute(
        """
        SELECT COUNT(*) FROM recovery_promises
        WHERE application_id = ? AND promise_status = 'fulfilled'
        """,
        (application_id,),
    )
    fulfilled_count = cursor.fetchone()[0] or 0
    return {
        "active_promise": dict(active) if active else None,
        "broken_count": broken_count,
        "fulfilled_count": fulfilled_count,
    }


def promise_queue_filter_sql(filter_key: str, alias: str = "a") -> tuple[str, list] | None:
    """Return SQL fragment and params for collections queue promise filters."""
    if filter_key == "overdue_promises":
        return (
            f"""
            EXISTS (
                SELECT 1 FROM recovery_promises rp
                WHERE rp.application_id = {alias}.id
                  AND rp.promise_status = 'active'
                  AND date(rp.promise_date) < date('now')
            )
            """,
            [],
        )
    if filter_key == "broken_commitments":
        return (
            f"""
            EXISTS (
                SELECT 1 FROM recovery_promises rp
                WHERE rp.application_id = {alias}.id
                  AND rp.promise_status = 'broken'
                  AND rp.broken_at IS NOT NULL
                  AND date(rp.broken_at) >= date('now', '-30 days')
            )
            """,
            [],
        )
    if filter_key == "promises_due_today":
        return (
            f"""
            EXISTS (
                SELECT 1 FROM recovery_promises rp
                WHERE rp.application_id = {alias}.id
                  AND rp.promise_status = 'active'
                  AND date(rp.promise_date) = date('now')
            )
            """,
            [],
        )
    if filter_key == "promises_due_week":
        return (
            f"""
            EXISTS (
                SELECT 1 FROM recovery_promises rp
                WHERE rp.application_id = {alias}.id
                  AND rp.promise_status = 'active'
                  AND date(rp.promise_date) BETWEEN date('now') AND date('now', '+7 days')
            )
            """,
            [],
        )
    return None


def count_orphaned_promise_history(cursor) -> int:
    cursor.execute(
        """
        SELECT COUNT(*) FROM recovery_promise_history ph
        WHERE NOT EXISTS (SELECT 1 FROM recovery_promises p WHERE p.id = ph.promise_id)
        """
    )
    return cursor.fetchone()[0] or 0


def count_orphaned_promises_application(cursor) -> int:
    cursor.execute(
        """
        SELECT COUNT(*) FROM recovery_promises rp
        WHERE NOT EXISTS (SELECT 1 FROM applications a WHERE a.id = rp.application_id)
        """
    )
    return cursor.fetchone()[0] or 0


def fetch_invalid_promise_statuses(cursor) -> list[str]:
    placeholders = ", ".join("?" * len(PROMISE_STATUSES))
    cursor.execute(
        f"""
        SELECT DISTINCT promise_status FROM recovery_promises
        WHERE promise_status NOT IN ({placeholders})
        LIMIT 10
        """,
        tuple(PROMISE_STATUSES),
    )
    return [row[0] for row in cursor.fetchall()]


def fetch_impossible_fulfillment_rows(cursor) -> int:
    cursor.execute(
        """
        SELECT COUNT(*) FROM recovery_promises
        WHERE promise_status = 'fulfilled'
          AND (fulfilled_at IS NULL OR TRIM(fulfilled_at) = '')
        """
    )
    return cursor.fetchone()[0] or 0


def fetch_unresolved_expired_active(cursor) -> int:
    cursor.execute(
        """
        SELECT COUNT(*) FROM recovery_promises
        WHERE promise_status = 'active'
          AND promise_date IS NOT NULL
          AND date(promise_date) < date('now', '-30 days')
        """
    )
    return cursor.fetchone()[0] or 0


def iter_active_promises_export(cursor, *, batch_size: int = 500):
    offset = 0
    while True:
        cursor.execute(
            """
            SELECT
                rp.id,
                rp.application_id,
                a.business_name,
                a.loan_account_number,
                rp.promise_amount,
                rp.promise_date,
                rp.promise_status,
                rp.commitment_notes,
                rp.created_by,
                rp.created_at,
                rp.fulfilled_at,
                rp.broken_at
            FROM recovery_promises rp
            INNER JOIN applications a ON a.id = rp.application_id
            WHERE rp.promise_status = 'active'
            ORDER BY rp.promise_date ASC, rp.id DESC
            LIMIT ? OFFSET ?
            """,
            (batch_size, offset),
        )
        rows = cursor.fetchall()
        if not rows:
            break
        for row in rows:
            yield dict(row)
        if len(rows) < batch_size:
            break
        offset += batch_size


def fetch_broken_commitments_export(cursor, limit: int) -> list[dict]:
    cursor.execute(
        """
        SELECT
            rp.id,
            rp.application_id,
            a.business_name,
            a.loan_account_number,
            rp.promise_amount,
            rp.promise_date,
            rp.promise_status,
            rp.created_by,
            rp.broken_at,
            rp.commitment_notes
        FROM recovery_promises rp
        INNER JOIN applications a ON a.id = rp.application_id
        WHERE rp.promise_status = 'broken'
        ORDER BY datetime(rp.broken_at) DESC, rp.id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(row) for row in cursor.fetchall()]


def fetch_overdue_commitments_export(cursor, limit: int) -> list[dict]:
    cursor.execute(
        """
        SELECT
            rp.id,
            rp.application_id,
            a.business_name,
            a.loan_account_number,
            rp.promise_amount,
            rp.promise_date,
            rp.created_by,
            rp.commitment_notes,
            CAST(julianday('now') - julianday(date(rp.promise_date)) AS INTEGER) AS days_overdue
        FROM recovery_promises rp
        INNER JOIN applications a ON a.id = rp.application_id
        WHERE rp.promise_status = 'active'
          AND date(rp.promise_date) < date('now')
        ORDER BY days_overdue DESC, rp.id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(row) for row in cursor.fetchall()]


def fetch_officer_promise_performance(cursor) -> list[dict]:
    cursor.execute(
        """
        SELECT
            created_by AS officer,
            COUNT(*) AS total_commitments,
            SUM(CASE WHEN promise_status = 'fulfilled' THEN 1 ELSE 0 END) AS fulfilled,
            SUM(CASE WHEN promise_status = 'broken' THEN 1 ELSE 0 END) AS broken,
            SUM(CASE WHEN promise_status = 'active' THEN 1 ELSE 0 END) AS active
        FROM recovery_promises
        WHERE created_by IS NOT NULL AND TRIM(created_by) != ''
        GROUP BY created_by
        ORDER BY total_commitments DESC
        LIMIT 15
        """
    )
    rows = []
    for row in cursor.fetchall():
        total = row["total_commitments"] or 0
        fulfilled = row["fulfilled"] or 0
        rows.append(
            {
                "officer": row["officer"],
                "total_commitments": total,
                "fulfilled": fulfilled,
                "broken": row["broken"] or 0,
                "active": row["active"] or 0,
                "fulfillment_rate_pct": round((fulfilled / total) * 100, 1) if total else 0.0,
            }
        )
    return rows


def fetch_commitment_aging_distribution(cursor) -> list[dict]:
    cursor.execute(
        """
        SELECT
            CASE
                WHEN promise_status != 'active' THEN 'not_active'
                WHEN date(promise_date) < date('now') THEN 'overdue'
                WHEN date(promise_date) = date('now') THEN 'due_today'
                WHEN date(promise_date) <= date('now', '+7 days') THEN 'due_this_week'
                ELSE 'future'
            END AS bucket,
            COUNT(*) AS count
        FROM recovery_promises
        GROUP BY bucket
        ORDER BY count DESC
        """
    )
    labels = {
        "overdue": "Overdue (active)",
        "due_today": "Due today",
        "due_this_week": "Due this week",
        "future": "Future active",
        "not_active": "Closed / terminal",
    }
    return [
        {"label": labels.get(row["bucket"], row["bucket"]), "bucket": row["bucket"], "count": row["count"]}
        for row in cursor.fetchall()
    ]


def fetch_repayment_conversion_rows(cursor, limit: int) -> list[dict]:
    cursor.execute(
        """
        SELECT
            rp.id AS promise_id,
            rp.application_id,
            a.business_name,
            rp.promise_amount,
            rp.promise_date,
            rp.promise_status,
            rp.fulfilled_at,
            (
                SELECT SUM(r.payment_amount) FROM repayments r
                WHERE r.application_id = rp.application_id
                  AND date(r.payment_date) >= date(rp.promise_date)
                  AND date(r.payment_date) <= date(COALESCE(rp.fulfilled_at, datetime('now')))
            ) AS repayments_after_promise
        FROM recovery_promises rp
        INNER JOIN applications a ON a.id = rp.application_id
        WHERE rp.promise_status IN ('fulfilled', 'broken', 'active')
        ORDER BY rp.id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(row) for row in cursor.fetchall()]
