import sqlite3

from constants.reporting import REPORT_EXPORT_MAX_ROWS
from constants.workflow import (
    KPI_ACTIVE_PIPELINE_STATUSES,
    KPI_APPROVED_STATUSES,
    KPI_CLIENT_ACTION_SUB_STATUSES,
    KPI_HIGH_RISK_LEVELS,
    KPI_OPS_REVIEW_SUB_STATUS,
    KPI_REJECTED_STATUS,
    OVERVIEW_LIST_LIMIT,
    OVERVIEW_OFFICER_LIMIT,
)
from repositories.database import get_db_connection
from repositories.loans import fetch_loan_portfolio_kpis


def fetch_executive_kpis(cursor) -> dict:
    pipeline_placeholders = ", ".join("?" * len(KPI_ACTIVE_PIPELINE_STATUSES))
    approved_placeholders = ", ".join("?" * len(KPI_APPROVED_STATUSES))
    high_risk_placeholders = ", ".join("?" * len(KPI_HIGH_RISK_LEVELS))
    client_placeholders = ", ".join("?" * len(KPI_CLIENT_ACTION_SUB_STATUSES))

    cursor.execute(
        f"""
        SELECT
            COUNT(*) AS total_applications,
            SUM(CASE WHEN status IN ({pipeline_placeholders}) THEN 1 ELSE 0 END)
                AS active_pipeline,
            SUM(CASE WHEN status IN ({approved_placeholders}) THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) AS rejected,
            SUM(CASE WHEN risk_level IN ({high_risk_placeholders}) THEN 1 ELSE 0 END) AS high_risk,
            SUM(CASE WHEN flagged_fraud = 1 THEN 1 ELSE 0 END) AS fraud_flagged,
            SUM(
                CASE
                    WHEN sub_status = ?
                        OR (
                            status IN ({pipeline_placeholders})
                            AND (assigned_officer IS NULL OR TRIM(assigned_officer) = '')
                        )
                    THEN 1
                    ELSE 0
                END
            ) AS pending_ops_review,
            SUM(CASE WHEN sub_status IN ({client_placeholders}) THEN 1 ELSE 0 END)
                AS awaiting_client_action
        FROM applications
        """,
        (
            *KPI_ACTIVE_PIPELINE_STATUSES,
            *KPI_APPROVED_STATUSES,
            KPI_REJECTED_STATUS,
            *KPI_HIGH_RISK_LEVELS,
            KPI_OPS_REVIEW_SUB_STATUS,
            *KPI_ACTIVE_PIPELINE_STATUSES,
            *KPI_CLIENT_ACTION_SUB_STATUSES,
        ),
    )
    row = cursor.fetchone()
    kpis = {
        "total_applications": row["total_applications"] or 0,
        "active_pipeline": row["active_pipeline"] or 0,
        "approved": row["approved"] or 0,
        "rejected": row["rejected"] or 0,
        "high_risk": row["high_risk"] or 0,
        "fraud_flagged": row["fraud_flagged"] or 0,
        "pending_ops_review": row["pending_ops_review"] or 0,
        "awaiting_client_action": row["awaiting_client_action"] or 0,
    }
    kpis.update(fetch_loan_portfolio_kpis(cursor))
    return kpis


def fetch_application_kpis(cursor) -> dict:
    executive = fetch_executive_kpis(cursor)
    return {
        "total_applications": executive["total_applications"],
        "pending_review": executive["active_pipeline"],
        "approved": executive["approved"],
        "rejected": executive["rejected"],
        "high_risk": executive["high_risk"],
        "fraud_flagged": executive["fraud_flagged"],
    }


def fetch_status_distribution(cursor) -> list[dict]:
    cursor.execute(
        """
        SELECT status, COUNT(*) AS count
        FROM applications
        GROUP BY status
        ORDER BY count DESC, status COLLATE NOCASE ASC
        """
    )
    return [{"label": row["status"], "count": row["count"]} for row in cursor.fetchall()]


def fetch_risk_distribution(cursor) -> list[dict]:
    cursor.execute(
        """
        SELECT risk_level, COUNT(*) AS count
        FROM applications
        GROUP BY risk_level
        ORDER BY count DESC, risk_level COLLATE NOCASE ASC
        """
    )
    return [{"label": row["risk_level"], "count": row["count"]} for row in cursor.fetchall()]


def fetch_pipeline_backlog(cursor) -> list[dict]:
    placeholders = ", ".join("?" * len(KPI_ACTIVE_PIPELINE_STATUSES))
    cursor.execute(
        f"""
        SELECT status, COUNT(*) AS count
        FROM applications
        WHERE status IN ({placeholders})
        GROUP BY status
        ORDER BY count DESC
        """,
        KPI_ACTIVE_PIPELINE_STATUSES,
    )
    return [{"label": row["status"], "count": row["count"]} for row in cursor.fetchall()]


def fetch_officer_workload(cursor, limit: int = OVERVIEW_OFFICER_LIMIT) -> list[dict]:
    pipeline_placeholders = ", ".join("?" * len(KPI_ACTIVE_PIPELINE_STATUSES))
    cursor.execute(
        f"""
        SELECT
            CASE
                WHEN assigned_officer IS NULL OR TRIM(assigned_officer) = ''
                THEN 'Unassigned'
                ELSE assigned_officer
            END AS officer_label,
            COUNT(*) AS total_count,
            SUM(CASE WHEN status IN ({pipeline_placeholders}) THEN 1 ELSE 0 END) AS pipeline_count,
            SUM(CASE WHEN flagged_fraud = 1 THEN 1 ELSE 0 END) AS fraud_count
        FROM applications
        GROUP BY officer_label
        ORDER BY pipeline_count DESC, total_count DESC, officer_label COLLATE NOCASE ASC
        LIMIT ?
        """,
        (*KPI_ACTIVE_PIPELINE_STATUSES, limit),
    )
    return [
        {
            "officer": row["officer_label"],
            "total_count": row["total_count"],
            "pipeline_count": row["pipeline_count"],
            "fraud_count": row["fraud_count"],
        }
        for row in cursor.fetchall()
    ]


def fetch_recent_applications(cursor, limit: int = OVERVIEW_LIST_LIMIT) -> list:
    cursor.execute(
        """
        SELECT
            id,
            business_name,
            owner_name,
            status,
            risk_level,
            created_at
        FROM applications
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return cursor.fetchall()


def fetch_attention_applications(cursor, limit: int = OVERVIEW_LIST_LIMIT) -> list:
    high_risk_placeholders = ", ".join("?" * len(KPI_HIGH_RISK_LEVELS))
    pipeline_placeholders = ", ".join("?" * len(KPI_ACTIVE_PIPELINE_STATUSES))
    cursor.execute(
        f"""
        SELECT
            id,
            business_name,
            owner_name,
            status,
            sub_status,
            risk_level,
            flagged_fraud,
            assigned_officer,
            updated_at
        FROM applications
        WHERE
            flagged_fraud = 1
            OR risk_level IN ({high_risk_placeholders})
            OR sub_status = ?
            OR (
                status IN ({pipeline_placeholders})
                AND (assigned_officer IS NULL OR TRIM(assigned_officer) = '')
            )
        ORDER BY
            flagged_fraud DESC,
            CASE risk_level
                WHEN 'Critical' THEN 4
                WHEN 'High' THEN 3
                WHEN 'Medium' THEN 2
                WHEN 'Low' THEN 1
                ELSE 0
            END DESC,
            datetime(updated_at) ASC,
            id ASC
        LIMIT ?
        """,
        (
            *KPI_HIGH_RISK_LEVELS,
            KPI_OPS_REVIEW_SUB_STATUS,
            *KPI_ACTIVE_PIPELINE_STATUSES,
            limit,
        ),
    )
    return cursor.fetchall()
_APPLICATION_EXPORT_SELECT = """
        SELECT
            id,
            business_name,
            owner_name,
            email,
            phone_number,
            revenue,
            product,
            status,
            sub_status,
            risk_level,
            flagged_fraud,
            assigned_officer,
            underwriting_status,
            decision_summary,
            reviewed_by,
            reviewed_at,
            loan_lifecycle_status,
            loan_account_number,
            issued_amount,
            outstanding_balance,
            repayment_progress,
            issue_date,
            due_date,
            repayment_frequency,
            repayment_risk_level,
            last_payment_at,
            created_at,
            updated_at
        FROM applications
"""

_APPLICATION_EXPORT_COLUMNS = (
    "id",
    "business_name",
    "owner_name",
    "email",
    "phone_number",
    "revenue",
    "product",
    "status",
    "sub_status",
    "risk_level",
    "flagged_fraud",
    "assigned_officer",
    "underwriting_status",
    "decision_summary",
    "reviewed_by",
    "reviewed_at",
    "loan_lifecycle_status",
    "loan_account_number",
    "issued_amount",
    "outstanding_balance",
    "repayment_progress",
    "issue_date",
    "due_date",
    "repayment_frequency",
    "repayment_risk_level",
    "last_payment_at",
    "created_at",
    "updated_at",
)


def count_applications_for_export(cursor, where_sql: str, where_params: list) -> int:
    cursor.execute(
        f"SELECT COUNT(*) FROM applications {where_sql}",
        where_params,
    )
    return cursor.fetchone()[0] or 0


def iter_applications_for_export(
    cursor,
    where_sql: str,
    where_params: list,
    limit: int = REPORT_EXPORT_MAX_ROWS,
):
    cursor.execute(
        f"""
{_APPLICATION_EXPORT_SELECT}
        {where_sql}
        ORDER BY id DESC
        LIMIT ?
        """,
        (*where_params, limit),
    )
    for row in cursor:
        yield {column: row[column] for column in _APPLICATION_EXPORT_COLUMNS}


def fetch_applications_for_export(
    cursor,
    where_sql: str,
    where_params: list,
    limit: int = REPORT_EXPORT_MAX_ROWS,
) -> list[dict]:
    return list(iter_applications_for_export(cursor, where_sql, where_params, limit))
def fetch_fraud_review_summary(cursor) -> dict:
    cursor.execute(
        """
        SELECT
            COUNT(*) AS fraud_flagged_total,
            SUM(CASE WHEN status IN ({}) THEN 1 ELSE 0 END) AS fraud_in_pipeline
        FROM applications
        WHERE flagged_fraud = 1
        """.format(", ".join("?" * len(KPI_ACTIVE_PIPELINE_STATUSES))),
        KPI_ACTIVE_PIPELINE_STATUSES,
    )
    row = cursor.fetchone()
    return {
        "fraud_flagged_total": row["fraud_flagged_total"] or 0,
        "fraud_in_pipeline": row["fraud_in_pipeline"] or 0,
    }
def fetch_application(application_id: int) -> sqlite3.Row | None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM applications WHERE id = ?", (application_id,))
    row = cursor.fetchone()
    conn.close()
    return row
