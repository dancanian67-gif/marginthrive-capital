import sqlite3

from constants.loans import (
    ACTIVE_LOAN_LIFECYCLE_STATUSES,
    DEFAULT_LOAN_LIFECYCLE_STATUS,
    DEFAULT_REPAYMENT_RISK_LEVEL,
    LOAN_LIFECYCLE_STATUSES,
    LOAN_LIFECYCLE_STATUS_LABELS,
)

REPAYMENT_HISTORY_LIMIT = 50
LOAN_ACCOUNT_HISTORY_LIMIT = 50


def init_repayments_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS repayments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            batch_id TEXT NOT NULL,
            payment_date TEXT NOT NULL,
            payment_amount REAL NOT NULL,
            balance_before REAL NOT NULL,
            balance_after REAL NOT NULL,
            repayment_notes TEXT NOT NULL DEFAULT '',
            actor TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_repayments_application
        ON repayments (application_id, datetime(payment_date) DESC, id DESC)
        """
    )


def init_loan_account_history_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS loan_account_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            batch_id TEXT NOT NULL,
            loan_lifecycle_status TEXT NOT NULL,
            loan_account_number TEXT NOT NULL DEFAULT '',
            issued_amount REAL,
            outstanding_balance REAL,
            repayment_progress REAL NOT NULL DEFAULT 0,
            issue_date TEXT,
            due_date TEXT,
            installment_amount REAL,
            repayment_frequency TEXT NOT NULL DEFAULT '',
            collections_notes TEXT NOT NULL DEFAULT '',
            missed_payment_observations TEXT NOT NULL DEFAULT '',
            repayment_risk_level TEXT NOT NULL DEFAULT 'current',
            actor TEXT NOT NULL,
            context_notes TEXT NOT NULL DEFAULT '',
            is_critical INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_loan_account_history_application
        ON loan_account_history (application_id, created_at DESC)
        """
    )


def _backfill_loan_defaults(cursor) -> None:
    cursor.execute(
        """
        UPDATE applications
        SET loan_lifecycle_status = ?
        WHERE loan_lifecycle_status IS NULL OR loan_lifecycle_status = ''
        """,
        (DEFAULT_LOAN_LIFECYCLE_STATUS,),
    )
    for column, default in (
        ("loan_account_number", ""),
        ("repayment_progress", 0),
        ("repayment_frequency", ""),
        ("collections_notes", ""),
        ("missed_payment_observations", ""),
        ("repayment_risk_level", DEFAULT_REPAYMENT_RISK_LEVEL),
    ):
        cursor.execute(
            f"""
            UPDATE applications
            SET {column} = ?
            WHERE {column} IS NULL
            """,
            (default,),
        )


def migrate_loan_columns(cursor) -> None:
    _backfill_loan_defaults(cursor)


def fetch_repayment_rows(cursor, application_id: int, limit: int = REPAYMENT_HISTORY_LIMIT) -> list[sqlite3.Row]:
    cursor.execute(
        """
        SELECT
            id,
            application_id,
            batch_id,
            payment_date,
            payment_amount,
            balance_before,
            balance_after,
            repayment_notes,
            actor,
            created_at
        FROM repayments
        WHERE application_id = ?
        ORDER BY datetime(payment_date) DESC, id DESC
        LIMIT ?
        """,
        (application_id, limit),
    )
    return cursor.fetchall()


def insert_repayment_record(
    cursor,
    *,
    application_id: int,
    batch_id: str,
    payment_date: str,
    payment_amount: float,
    balance_before: float,
    balance_after: float,
    repayment_notes: str,
    actor: str,
) -> None:
    cursor.execute(
        """
        INSERT INTO repayments (
            application_id,
            batch_id,
            payment_date,
            payment_amount,
            balance_before,
            balance_after,
            repayment_notes,
            actor
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            application_id,
            batch_id,
            payment_date,
            payment_amount,
            balance_before,
            balance_after,
            repayment_notes,
            actor,
        ),
    )


def insert_loan_account_history_record(
    cursor,
    *,
    application_id: int,
    batch_id: str,
    snapshot: dict,
    actor: str,
    context_notes: str,
    is_critical: int,
) -> None:
    cursor.execute(
        """
        INSERT INTO loan_account_history (
            application_id,
            batch_id,
            loan_lifecycle_status,
            loan_account_number,
            issued_amount,
            outstanding_balance,
            repayment_progress,
            issue_date,
            due_date,
            installment_amount,
            repayment_frequency,
            collections_notes,
            missed_payment_observations,
            repayment_risk_level,
            actor,
            context_notes,
            is_critical
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            application_id,
            batch_id,
            snapshot["loan_lifecycle_status"],
            snapshot["loan_account_number"],
            snapshot["issued_amount"],
            snapshot["outstanding_balance"],
            snapshot["repayment_progress"],
            snapshot["issue_date"],
            snapshot["due_date"],
            snapshot["installment_amount"],
            snapshot["repayment_frequency"],
            snapshot["collections_notes"],
            snapshot["missed_payment_observations"],
            snapshot["repayment_risk_level"],
            actor,
            context_notes,
            is_critical,
        ),
    )


def fetch_loan_account_history_rows(
    cursor,
    application_id: int,
    limit: int = LOAN_ACCOUNT_HISTORY_LIMIT,
) -> list[sqlite3.Row]:
    cursor.execute(
        """
        SELECT
            id,
            application_id,
            batch_id,
            loan_lifecycle_status,
            loan_account_number,
            issued_amount,
            outstanding_balance,
            repayment_progress,
            issue_date,
            due_date,
            installment_amount,
            repayment_frequency,
            collections_notes,
            missed_payment_observations,
            repayment_risk_level,
            actor,
            context_notes,
            is_critical,
            created_at
        FROM loan_account_history
        WHERE application_id = ?
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT ?
        """,
        (application_id, limit),
    )
    return cursor.fetchall()


def fetch_loan_lifecycle_distribution(cursor) -> list[dict]:
    cursor.execute(
        """
        SELECT loan_lifecycle_status AS label, COUNT(*) AS count
        FROM applications
        GROUP BY loan_lifecycle_status
        """
    )
    rows = cursor.fetchall()
    order_index = {status: index for index, status in enumerate(LOAN_LIFECYCLE_STATUSES)}
    items = []
    for row in rows:
        code = row["label"]
        items.append(
            {
                "label": LOAN_LIFECYCLE_STATUS_LABELS.get(code, code),
                "code": code,
                "count": row["count"],
            }
        )
    items.sort(key=lambda item: order_index.get(item["code"], 99))
    return items


def fetch_loan_portfolio_kpis(cursor) -> dict:
    active_placeholders = ", ".join("?" * len(ACTIVE_LOAN_LIFECYCLE_STATUSES))
    cursor.execute(
        f"""
        SELECT
            SUM(
                CASE WHEN loan_lifecycle_status IN ({active_placeholders}) THEN 1 ELSE 0 END
            ) AS active_loans,
            SUM(CASE WHEN loan_lifecycle_status = 'overdue' THEN 1 ELSE 0 END) AS overdue_loans,
            SUM(
                CASE
                    WHEN loan_lifecycle_status IN ('active', 'repaying')
                        AND due_date IS NOT NULL
                        AND TRIM(due_date) != ''
                        AND date(due_date) < date('now')
                        AND COALESCE(outstanding_balance, 0) > 0
                    THEN 1
                    ELSE 0
                END
            ) AS delinquent_not_marked_overdue,
            SUM(
                CASE
                    WHEN loan_lifecycle_status IN ({active_placeholders})
                    THEN COALESCE(outstanding_balance, 0)
                    ELSE 0
                END
            ) AS total_outstanding,
            SUM(
                CASE WHEN loan_lifecycle_status = 'completed' THEN 1 ELSE 0 END
            ) AS completed_loans,
            SUM(
                CASE WHEN loan_lifecycle_status IN ('defaulted', 'written_off') THEN 1 ELSE 0 END
            ) AS distressed_loans
        FROM applications
        """,
        (*ACTIVE_LOAN_LIFECYCLE_STATUSES, *ACTIVE_LOAN_LIFECYCLE_STATUSES),
    )
    row = cursor.fetchone()
    overdue = (row["overdue_loans"] or 0) + (row["delinquent_not_marked_overdue"] or 0)
    return {
        "active_loans": row["active_loans"] or 0,
        "overdue_loans": overdue,
        "total_outstanding": round(row["total_outstanding"] or 0, 2),
        "completed_loans": row["completed_loans"] or 0,
        "distressed_loans": row["distressed_loans"] or 0,
    }


_REPAYMENT_EXPORT_COLUMNS = (
    "id",
    "application_id",
    "business_name",
    "loan_account_number",
    "payment_date",
    "payment_amount",
    "balance_before",
    "balance_after",
    "repayment_notes",
    "actor",
    "created_at",
)


def count_repayments_for_export(cursor, where_sql: str, where_params: list) -> int:
    cursor.execute(
        f"""
        SELECT COUNT(*)
        FROM repayments r
        INNER JOIN applications a ON a.id = r.application_id
        {where_sql}
        """,
        where_params,
    )
    return cursor.fetchone()[0] or 0


def iter_repayments_for_export(
    cursor,
    where_sql: str,
    where_params: list,
    limit: int,
):
    cursor.execute(
        f"""
        SELECT
            r.id,
            r.application_id,
            a.business_name,
            a.loan_account_number,
            r.payment_date,
            r.payment_amount,
            r.balance_before,
            r.balance_after,
            r.repayment_notes,
            r.actor,
            r.created_at
        FROM repayments r
        INNER JOIN applications a ON a.id = r.application_id
        {where_sql}
        ORDER BY datetime(r.payment_date) DESC, r.id DESC
        LIMIT ?
        """,
        (*where_params, limit),
    )
    for row in cursor:
        yield {column: row[column] for column in _REPAYMENT_EXPORT_COLUMNS}


def fetch_repayments_for_export(
    cursor,
    where_sql: str,
    where_params: list,
    limit: int,
) -> list[dict]:
    return list(iter_repayments_for_export(cursor, where_sql, where_params, limit))
