"""Portfolio intelligence SQL aggregations (Phase E1)."""

from constants.loans import ACTIVE_LOAN_LIFECYCLE_STATUSES
from constants.portfolio import COLLECTIONS_RISK_LEVELS, DISTRESSED_LOAN_STATUSES, ISSUED_LOAN_STATUSES
from constants.underwriting import UNDERWRITING_STATUS_LABELS
from services.analytics_query import analytics_datetime_clause

_ACTIVE_IN = ", ".join(f"'{s}'" for s in ACTIVE_LOAN_LIFECYCLE_STATUSES)
_DISTRESSED_IN = ", ".join(f"'{s}'" for s in DISTRESSED_LOAN_STATUSES)
_ISSUED_IN = ", ".join(f"'{s}'" for s in ISSUED_LOAN_STATUSES)
_COLLECTIONS_IN = ", ".join(f"'{s}'" for s in COLLECTIONS_RISK_LEVELS)


def fetch_portfolio_financial_snapshot(cursor) -> dict:
    cursor.execute(
        f"""
        SELECT
            SUM(
                CASE WHEN loan_lifecycle_status IN ({_ACTIVE_IN})
                THEN COALESCE(issued_amount, 0) ELSE 0 END
            ) AS active_portfolio_value,
            SUM(
                CASE WHEN loan_lifecycle_status IN ({_ACTIVE_IN})
                THEN COALESCE(outstanding_balance, 0) ELSE 0 END
            ) AS total_outstanding,
            SUM(
                CASE WHEN loan_lifecycle_status IN ({_ISSUED_IN})
                THEN COALESCE(issued_amount, 0) ELSE 0 END
            ) AS total_issued_capital,
            SUM(
                CASE WHEN loan_lifecycle_status IN ({_ACTIVE_IN})
                THEN COALESCE(repayment_progress, 0) ELSE 0 END
            ) AS progress_sum_active,
            COUNT(CASE WHEN loan_lifecycle_status IN ({_ACTIVE_IN}) THEN 1 END) AS active_loan_count,
            SUM(
                CASE WHEN loan_lifecycle_status IN ({_DISTRESSED_IN})
                THEN COALESCE(outstanding_balance, 0) ELSE 0 END
            ) AS default_exposure,
            SUM(
                CASE
                    WHEN loan_lifecycle_status = 'overdue'
                        OR (
                            loan_lifecycle_status IN ('active', 'repaying')
                            AND due_date IS NOT NULL AND TRIM(due_date) != ''
                            AND date(due_date) < date('now')
                            AND COALESCE(outstanding_balance, 0) > 0
                        )
                    THEN COALESCE(outstanding_balance, 0) ELSE 0
                END
            ) AS overdue_exposure,
            SUM(
                CASE
                    WHEN loan_lifecycle_status IN ({_DISTRESSED_IN})
                        OR (
                            loan_lifecycle_status IN ({_ACTIVE_IN})
                            AND repayment_risk_level IN ({_COLLECTIONS_IN})
                        )
                        OR (
                            loan_lifecycle_status IN ('active', 'repaying')
                            AND due_date IS NOT NULL AND TRIM(due_date) != ''
                            AND date(due_date) < date('now')
                            AND COALESCE(outstanding_balance, 0) > 0
                        )
                    THEN COALESCE(outstanding_balance, 0) ELSE 0
                END
            ) AS collections_exposure,
            COUNT(CASE WHEN loan_lifecycle_status = 'completed' THEN 1 END) AS completed_loan_count,
            COUNT(CASE WHEN loan_lifecycle_status IN ({_DISTRESSED_IN}) THEN 1 END) AS distressed_loan_count,
            COUNT(
                CASE
                    WHEN loan_lifecycle_status = 'overdue'
                        OR (
                            loan_lifecycle_status IN ('active', 'repaying')
                            AND due_date IS NOT NULL AND TRIM(due_date) != ''
                            AND date(due_date) < date('now')
                            AND COALESCE(outstanding_balance, 0) > 0
                        )
                    THEN 1
                END
            ) AS overdue_loan_count,
            COUNT(CASE WHEN loan_lifecycle_status IN ({_ISSUED_IN}) THEN 1 END) AS issued_loan_count
        FROM applications
        """
    )
    row = cursor.fetchone()

    cursor.execute("SELECT COALESCE(SUM(payment_amount), 0) AS total_repaid FROM repayments")
    total_repaid = cursor.fetchone()["total_repaid"] or 0

    active_count = row["active_loan_count"] or 0
    avg_progress = round((row["progress_sum_active"] or 0) / active_count, 1) if active_count else 0.0

    total_issued = row["total_issued_capital"] or 0
    repayment_completion_ratio = round((total_repaid / total_issued) * 100, 1) if total_issued > 0 else 0.0

    issued_loan_count = row["issued_loan_count"] or 0
    completed_count = row["completed_loan_count"] or 0
    loan_completion_rate = round((completed_count / issued_loan_count) * 100, 1) if issued_loan_count else 0.0

    overdue_loans = row["overdue_loan_count"] or 0
    delinquency_ratio = round((overdue_loans / active_count) * 100, 1) if active_count else 0.0

    return {
        "active_portfolio_value": round(row["active_portfolio_value"] or 0, 2),
        "total_outstanding": round(row["total_outstanding"] or 0, 2),
        "total_issued_capital": round(total_issued, 2),
        "total_repaid_capital": round(total_repaid, 2),
        "repayment_completion_ratio": repayment_completion_ratio,
        "avg_repayment_progress_active": avg_progress,
        "loan_completion_rate": loan_completion_rate,
        "overdue_exposure": round(row["overdue_exposure"] or 0, 2),
        "default_exposure": round(row["default_exposure"] or 0, 2),
        "collections_exposure": round(row["collections_exposure"] or 0, 2),
        "active_loan_count": active_count,
        "overdue_loan_count": overdue_loans,
        "completed_loan_count": completed_count,
        "distressed_loan_count": row["distressed_loan_count"] or 0,
        "issued_loan_count": issued_loan_count,
        "delinquency_ratio": delinquency_ratio,
    }


def fetch_portfolio_aging_distribution(cursor) -> list[dict]:
    from constants.portfolio import PORTFOLIO_AGING_LABELS

    cursor.execute(
        f"""
        SELECT
            CASE
                WHEN due_date IS NULL OR TRIM(due_date) = '' THEN 'no_due_date'
                WHEN date(due_date) >= date('now') THEN 'current'
                WHEN julianday('now') - julianday(due_date) <= 30 THEN '1_30_days'
                WHEN julianday('now') - julianday(due_date) <= 60 THEN '31_60_days'
                WHEN julianday('now') - julianday(due_date) <= 90 THEN '61_90_days'
                ELSE '90_plus_days'
            END AS bucket,
            COUNT(*) AS count,
            SUM(COALESCE(outstanding_balance, 0)) AS exposure
        FROM applications
        WHERE loan_lifecycle_status IN ({_ACTIVE_IN})
          AND COALESCE(outstanding_balance, 0) > 0
        GROUP BY bucket
        """
    )
    order = ("current", "1_30_days", "31_60_days", "61_90_days", "90_plus_days", "no_due_date")
    index = {b: i for i, b in enumerate(order)}
    items = []
    for row in cursor.fetchall():
        bucket = row["bucket"]
        items.append(
            {
                "label": PORTFOLIO_AGING_LABELS.get(bucket, bucket),
                "code": bucket,
                "count": row["count"],
                "exposure": round(row["exposure"] or 0, 2),
            }
        )
    items.sort(key=lambda x: index.get(x["code"], 99))
    return items


def fetch_repayment_trend(cursor, range_key: str) -> list[dict]:
    clause, params = analytics_datetime_clause(range_key, "payment_date")
    cursor.execute(
        f"""
        SELECT
            date(payment_date) AS day_label,
            COUNT(*) AS payment_count,
            COALESCE(SUM(payment_amount), 0) AS amount_total
        FROM repayments
        WHERE payment_date IS NOT NULL AND TRIM(payment_date) != ''{clause}
        GROUP BY date(payment_date)
        ORDER BY day_label ASC
        LIMIT 90
        """,
        params,
    )
    return [
        {
            "label": row["day_label"],
            "count": row["payment_count"],
            "amount": round(row["amount_total"] or 0, 2),
        }
        for row in cursor.fetchall()
    ]


def fetch_underwriting_decision_trend(cursor, range_key: str) -> list[dict]:
    clause, params = analytics_datetime_clause(range_key, "reviewed_at")
    cursor.execute(
        f"""
        SELECT date(reviewed_at) AS day_label, underwriting_status AS status, COUNT(*) AS count
        FROM applications
        WHERE reviewed_at IS NOT NULL AND TRIM(reviewed_at) != ''{clause}
        GROUP BY date(reviewed_at), underwriting_status
        ORDER BY day_label ASC
        LIMIT 500
        """,
        params,
    )
    return [
        {
            "label": row["day_label"],
            "status": row["status"],
            "status_label": UNDERWRITING_STATUS_LABELS.get(row["status"], row["status"]),
            "count": row["count"],
        }
        for row in cursor.fetchall()
    ]


def fetch_underwriting_outcome_summary(cursor, range_key: str) -> dict:
    clause, params = analytics_datetime_clause(range_key, "reviewed_at")
    cursor.execute(
        f"""
        SELECT
            COUNT(*) AS total_reviewed,
            SUM(CASE WHEN underwriting_status IN ('approved', 'conditionally_approved') THEN 1 ELSE 0 END)
                AS approved,
            SUM(CASE WHEN underwriting_status = 'rejected' THEN 1 ELSE 0 END) AS rejected,
            SUM(CASE WHEN underwriting_status = 'escalated_review' THEN 1 ELSE 0 END) AS escalated,
            SUM(CASE WHEN underwriting_status = 'pending_clarification' THEN 1 ELSE 0 END) AS clarification,
            SUM(CASE WHEN underwriting_status = 'conditionally_approved' THEN 1 ELSE 0 END) AS conditional
        FROM applications
        WHERE reviewed_at IS NOT NULL AND TRIM(reviewed_at) != ''{clause}
        """,
        params,
    )
    row = cursor.fetchone()
    total = row["total_reviewed"] or 0
    approved = row["approved"] or 0
    rejected = row["rejected"] or 0
    return {
        "total_reviewed": total,
        "approved": approved,
        "rejected": rejected,
        "escalated": row["escalated"] or 0,
        "clarification": row["clarification"] or 0,
        "conditional": row["conditional"] or 0,
        "approval_rate": round((approved / total) * 100, 1) if total else 0.0,
        "rejection_rate": round((rejected / total) * 100, 1) if total else 0.0,
    }


def fetch_collections_workload(cursor) -> list[dict]:
    cursor.execute(
        f"""
        SELECT
            CASE
                WHEN assigned_officer IS NULL OR TRIM(assigned_officer) = '' THEN 'Unassigned'
                ELSE assigned_officer
            END AS officer_label,
            COUNT(*) AS collections_cases,
            SUM(COALESCE(outstanding_balance, 0)) AS exposure
        FROM applications
        WHERE
            loan_lifecycle_status IN ({_DISTRESSED_IN})
            OR (
                loan_lifecycle_status IN ({_ACTIVE_IN})
                AND repayment_risk_level IN ({_COLLECTIONS_IN})
            )
            OR (
                loan_lifecycle_status IN ('active', 'repaying')
                AND due_date IS NOT NULL AND TRIM(due_date) != ''
                AND date(due_date) < date('now')
                AND COALESCE(outstanding_balance, 0) > 0
            )
        GROUP BY officer_label
        ORDER BY exposure DESC, collections_cases DESC
        LIMIT 10
        """
    )
    return [
        {
            "officer": row["officer_label"],
            "collections_cases": row["collections_cases"],
            "exposure": round(row["exposure"] or 0, 2),
        }
        for row in cursor.fetchall()
    ]


def fetch_operational_throughput(cursor, range_key: str) -> dict:
    created_clause, created_params = analytics_datetime_clause(range_key, "created_at")
    repayment_clause, repayment_params = analytics_datetime_clause(range_key, "payment_date")
    issue_clause, issue_params = analytics_datetime_clause(range_key, "issue_date")

    cursor.execute(
        f"""
        SELECT COUNT(*) AS applications_created
        FROM applications
        WHERE created_at IS NOT NULL AND created_at != ''{created_clause}
        """,
        created_params,
    )
    applications_created = cursor.fetchone()["applications_created"] or 0

    cursor.execute(
        f"""
        SELECT COUNT(*) AS loans_activated
        FROM applications
        WHERE loan_lifecycle_status IN ({_ISSUED_IN})
          AND issue_date IS NOT NULL AND TRIM(issue_date) != ''{issue_clause}
        """,
        issue_params,
    )
    loans_activated = cursor.fetchone()["loans_activated"] or 0

    cursor.execute(
        f"""
        SELECT COUNT(*) AS repayments_recorded, COALESCE(SUM(payment_amount), 0) AS repayment_volume
        FROM repayments
        WHERE payment_date IS NOT NULL AND TRIM(payment_date) != ''{repayment_clause}
        """,
        repayment_params,
    )
    rep_row = cursor.fetchone()
    return {
        "applications_created": applications_created,
        "loans_activated": loans_activated,
        "repayments_recorded": rep_row["repayments_recorded"] or 0,
        "repayment_volume": round(rep_row["repayment_volume"] or 0, 2),
    }


def fetch_repayment_performance_period(cursor, range_key: str) -> dict:
    repayment_clause, repayment_params = analytics_datetime_clause(range_key, "payment_date")
    cursor.execute(
        f"""
        SELECT
            COUNT(*) AS payment_count,
            COALESCE(SUM(payment_amount), 0) AS payment_total,
            COALESCE(AVG(payment_amount), 0) AS payment_avg
        FROM repayments
        WHERE payment_date IS NOT NULL AND TRIM(payment_date) != ''{repayment_clause}
        """,
        repayment_params,
    )
    row = cursor.fetchone()
    snapshot = fetch_portfolio_financial_snapshot(cursor)
    return {
        "payment_count": row["payment_count"] or 0,
        "payment_total": round(row["payment_total"] or 0, 2),
        "payment_avg": round(row["payment_avg"] or 0, 2),
        "delinquency_ratio": snapshot["delinquency_ratio"],
    }
