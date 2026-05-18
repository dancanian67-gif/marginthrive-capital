import sqlite3

from constants.underwriting import DEFAULT_UNDERWRITING_STATUS, UNDERWRITING_STATUSES

UNDERWRITING_HISTORY_LIMIT = 50


def init_underwriting_decisions_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS underwriting_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            batch_id TEXT NOT NULL,
            underwriting_status TEXT NOT NULL,
            affordability_assessment TEXT NOT NULL,
            repayment_confidence TEXT NOT NULL,
            business_stability_review TEXT NOT NULL,
            documentation_quality_review TEXT NOT NULL,
            operational_risk_observations TEXT NOT NULL DEFAULT '',
            fraud_concern_observations TEXT NOT NULL DEFAULT '',
            underwriting_notes TEXT NOT NULL DEFAULT '',
            decision_summary TEXT NOT NULL DEFAULT '',
            decision_reason TEXT NOT NULL DEFAULT '',
            escalation_reason TEXT NOT NULL DEFAULT '',
            reviewed_by TEXT NOT NULL,
            actor TEXT NOT NULL,
            context_notes TEXT NOT NULL DEFAULT '',
            is_critical INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_underwriting_decisions_application
        ON underwriting_decisions (application_id, created_at DESC)
        """
    )


def _backfill_underwriting_defaults(cursor) -> None:
    cursor.execute(
        """
        UPDATE applications
        SET underwriting_status = ?
        WHERE underwriting_status IS NULL OR underwriting_status = ''
        """,
        (DEFAULT_UNDERWRITING_STATUS,),
    )
    for column, default in (
        ("affordability_assessment", "not_assessed"),
        ("repayment_confidence", "not_assessed"),
        ("business_stability_review", "not_assessed"),
        ("documentation_quality_review", "not_assessed"),
        ("operational_risk_observations", ""),
        ("fraud_concern_observations", ""),
        ("underwriting_notes", ""),
        ("decision_summary", ""),
        ("decision_reason", ""),
        ("reviewed_by", ""),
        ("escalation_reason", ""),
    ):
        cursor.execute(
            f"""
            UPDATE applications
            SET {column} = ?
            WHERE {column} IS NULL
            """,
            (default,),
        )


def migrate_underwriting_columns(cursor) -> None:
    _backfill_underwriting_defaults(cursor)


def fetch_underwriting_decision_history(
    cursor,
    application_id: int,
    limit: int = UNDERWRITING_HISTORY_LIMIT,
) -> list[sqlite3.Row]:
    cursor.execute(
        """
        SELECT
            id,
            application_id,
            batch_id,
            underwriting_status,
            affordability_assessment,
            repayment_confidence,
            business_stability_review,
            documentation_quality_review,
            operational_risk_observations,
            fraud_concern_observations,
            underwriting_notes,
            decision_summary,
            decision_reason,
            escalation_reason,
            reviewed_by,
            actor,
            context_notes,
            is_critical,
            created_at
        FROM underwriting_decisions
        WHERE application_id = ?
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT ?
        """,
        (application_id, limit),
    )
    return cursor.fetchall()


def insert_underwriting_decision_record(
    cursor,
    *,
    application_id: int,
    batch_id: str,
    snapshot: dict,
    actor: str,
    reviewed_by: str,
    context_notes: str,
    is_critical: int,
) -> None:
    cursor.execute(
        """
        INSERT INTO underwriting_decisions (
            application_id,
            batch_id,
            underwriting_status,
            affordability_assessment,
            repayment_confidence,
            business_stability_review,
            documentation_quality_review,
            operational_risk_observations,
            fraud_concern_observations,
            underwriting_notes,
            decision_summary,
            decision_reason,
            escalation_reason,
            reviewed_by,
            actor,
            context_notes,
            is_critical
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            application_id,
            batch_id,
            snapshot["underwriting_status"],
            snapshot["affordability_assessment"],
            snapshot["repayment_confidence"],
            snapshot["business_stability_review"],
            snapshot["documentation_quality_review"],
            snapshot["operational_risk_observations"],
            snapshot["fraud_concern_observations"],
            snapshot["underwriting_notes"],
            snapshot["decision_summary"],
            snapshot["decision_reason"],
            snapshot["escalation_reason"],
            reviewed_by,
            actor,
            context_notes,
            is_critical,
        ),
    )


def fetch_underwriting_portfolio_distribution(cursor) -> list[dict]:
    from constants.underwriting import UNDERWRITING_STATUS_LABELS

    items = fetch_underwriting_status_distribution(cursor)
    for item in items:
        item["label"] = UNDERWRITING_STATUS_LABELS.get(item["label"], item["label"])
    return items


def fetch_underwriting_status_distribution(cursor) -> list[dict]:
    cursor.execute(
        """
        SELECT underwriting_status AS label, COUNT(*) AS count
        FROM applications
        GROUP BY underwriting_status
        """
    )
    rows = cursor.fetchall()
    order_index = {status: index for index, status in enumerate(UNDERWRITING_STATUSES)}
    items = [{"label": row["label"], "count": row["count"]} for row in rows]
    items.sort(key=lambda item: order_index.get(item["label"], 99))
    return items


def fetch_underwriting_period_counts(cursor, reviewed_clause: str, reviewed_params: list) -> dict:
    cursor.execute(
        f"""
        SELECT
            COUNT(*) AS total_reviewed,
            SUM(CASE WHEN underwriting_status IN ('approved', 'conditionally_approved') THEN 1 ELSE 0 END)
                AS approved_decisions,
            SUM(CASE WHEN underwriting_status = 'rejected' THEN 1 ELSE 0 END) AS rejected_decisions,
            SUM(CASE WHEN underwriting_status = 'escalated_review' THEN 1 ELSE 0 END) AS escalated_decisions,
            SUM(CASE WHEN underwriting_status = 'pending_clarification' THEN 1 ELSE 0 END) AS clarification_decisions
        FROM applications
        WHERE reviewed_at IS NOT NULL AND reviewed_at != ''{reviewed_clause}
        """,
        reviewed_params,
    )
    row = cursor.fetchone()
    return {
        "total_reviewed": row["total_reviewed"] or 0,
        "approved_decisions": row["approved_decisions"] or 0,
        "rejected_decisions": row["rejected_decisions"] or 0,
        "escalated_decisions": row["escalated_decisions"] or 0,
        "clarification_decisions": row["clarification_decisions"] or 0,
    }
