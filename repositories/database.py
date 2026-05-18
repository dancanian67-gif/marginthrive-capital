import sqlite3

from constants.app import DATABASE_PATH
from constants.schema import APPLICATIONS_SCHEMA_COLUMNS
from constants.workflow import DEFAULT_APPLICATION_STATUS, DEFAULT_RISK_LEVEL

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _applications_column_names(cursor) -> set[str]:
    cursor.execute("PRAGMA table_info(applications)")
    return {row[1] for row in cursor.fetchall()}


def _migrate_applications_table(cursor) -> None:
    existing = _applications_column_names(cursor)
    if not existing:
        return

    for column_name, column_def in APPLICATIONS_SCHEMA_COLUMNS:
        if column_name not in existing:
            cursor.execute(f"ALTER TABLE applications ADD COLUMN {column_name} {column_def}")

    cursor.execute(
        """
        UPDATE applications
        SET created_at = datetime('now')
        WHERE created_at IS NULL OR created_at = ''
        """
    )
    cursor.execute(
        """
        UPDATE applications
        SET updated_at = datetime('now')
        WHERE updated_at IS NULL OR updated_at = ''
        """
    )
    cursor.execute(
        """
        UPDATE applications
        SET status = ?
        WHERE status IS NULL OR status = ''
        """,
        (DEFAULT_APPLICATION_STATUS,),
    )
    cursor.execute(
        """
        UPDATE applications
        SET risk_level = ?
        WHERE risk_level IS NULL OR risk_level = ''
        """,
        (DEFAULT_RISK_LEVEL,),
    )
    cursor.execute(
        """
        UPDATE applications
        SET flagged_fraud = 0
        WHERE flagged_fraud IS NULL
        """
    )


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_name TEXT NOT NULL,
            owner_name TEXT NOT NULL,
            email TEXT NOT NULL,
            revenue REAL NOT NULL,
            product TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'New applicant',
            sub_status TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            risk_level TEXT NOT NULL DEFAULT 'Unassigned',
            approval_notes TEXT NOT NULL DEFAULT '',
            assigned_officer TEXT NOT NULL DEFAULT '',
            phone_number TEXT NOT NULL DEFAULT '',
            business_type TEXT NOT NULL DEFAULT '',
            date_of_birth TEXT,
            gender TEXT NOT NULL DEFAULT '',
            flagged_fraud INTEGER NOT NULL DEFAULT 0,
            loan_amount REAL
        )
        """
    )

    _migrate_applications_table(cursor)
    from repositories.audit import init_workflow_history_table
    from repositories.officers import init_officers_table, seed_officers_table
    from repositories.operators import init_operators_table, seed_bootstrap_operator
    from repositories.loans import (
        init_loan_account_history_table,
        init_repayments_table,
        migrate_loan_columns,
    )
    from repositories.underwriting import init_underwriting_decisions_table, migrate_underwriting_columns

    init_workflow_history_table(cursor)
    init_underwriting_decisions_table(cursor)
    init_repayments_table(cursor)
    init_loan_account_history_table(cursor)
    init_officers_table(cursor)
    seed_officers_table(cursor)
    init_operators_table(cursor)
    seed_bootstrap_operator(cursor)
    migrate_underwriting_columns(cursor)
    migrate_loan_columns(cursor)

    conn.commit()
    conn.close()
