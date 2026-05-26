"""Idempotent performance indexes for operational queries (Phase E2)."""

from constants.ops import PERFORMANCE_INDEX_NAMES


def init_performance_indexes(cursor) -> None:
    """Create indexes safely on every startup; no data is modified or removed."""

    # applications — list filters, analytics grouping, export ordering
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_applications_created_at
        ON applications (created_at)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_applications_status
        ON applications (status)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_applications_risk_level
        ON applications (risk_level)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_applications_assigned_officer
        ON applications (assigned_officer)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_applications_underwriting_status
        ON applications (underwriting_status)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_applications_loan_lifecycle_status
        ON applications (loan_lifecycle_status)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_applications_reviewed_at
        ON applications (reviewed_at)
        """
    )

    # workflow_history — timeline, audit export, governance summaries
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workflow_history_created_at
        ON workflow_history (created_at)
        """
    )

    # underwriting_decisions — history panels (created_at; applications holds reviewed_at)
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_underwriting_decisions_reviewed_at
        ON underwriting_decisions (application_id, created_at DESC)
        """
    )

    # repayments — servicing history and exports (payment_date column)
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_repayments_payment_date
        ON repayments (application_id, payment_date)
        """
    )

    # loan_account_history — servicing timeline
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_loan_account_history_created_at
        ON loan_account_history (created_at)
        """
    )

    # operators — login lookup and active operator listings
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_operators_username
        ON operators (username COLLATE NOCASE)
        """
    )


def fetch_existing_index_names(cursor) -> set[str]:
    cursor.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type = 'index' AND name NOT LIKE 'sqlite_%'
        """
    )
    return {row[0] for row in cursor.fetchall()}


def verify_performance_indexes(cursor) -> list[str]:
    """Return names of expected performance indexes that are missing."""
    existing = fetch_existing_index_names(cursor)
    return [name for name in PERFORMANCE_INDEX_NAMES if name not in existing]
