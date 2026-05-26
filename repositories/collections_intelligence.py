"""Collections intelligence queries (Phase F2)."""

import sqlite3

from repositories.collections import (
    _delinquency_bucket_sql,
    _delinquency_days_sql,
    collections_queue_predicate,
)
from services.collections_priority import intelligence_score_sql


def fetch_application_intelligence_context(
    cursor,
    application_ids: list[int],
) -> dict[int, dict]:
    """Batch-load repayment and escalation aggregates for queue scoring."""
    if not application_ids:
        return {}
    placeholders = ", ".join("?" * len(application_ids))
    cursor.execute(
        f"""
        SELECT
            a.id AS application_id,
            (SELECT COUNT(*) FROM repayments r WHERE r.application_id = a.id) AS repayment_count,
            (
                SELECT COALESCE(SUM(r.payment_amount), 0)
                FROM repayments r
                WHERE r.application_id = a.id
                  AND r.payment_date IS NOT NULL
                  AND date(r.payment_date) >= date('now', '-90 days')
            ) AS recent_payment_amount,
            (
                SELECT COUNT(*) FROM collections_history ch
                WHERE ch.application_id = a.id AND ch.is_critical = 1
            ) AS escalation_count
        FROM applications a
        WHERE a.id IN ({placeholders})
        """,
        application_ids,
    )
    return {
        row["application_id"]: {
            "repayment_count": row["repayment_count"] or 0,
            "recent_payment_amount": float(row["recent_payment_amount"] or 0),
            "escalation_count": row["escalation_count"] or 0,
        }
        for row in cursor.fetchall()
    }


def fetch_collections_queue_intelligence_sorted(
    cursor,
    filters: dict,
    *,
    limit: int,
    offset: int,
) -> list[sqlite3.Row]:
    """Queue fetch ordered by intelligence score approximation."""
    from repositories.collections import build_collections_where

    where_sql, params = build_collections_where(filters)
    days_sql = _delinquency_days_sql("a")
    bucket_sql = _delinquency_bucket_sql("a")
    score_sql = intelligence_score_sql("a")
    cursor.execute(
        f"""
        SELECT
            a.*,
            {days_sql} AS days_overdue,
            {bucket_sql} AS delinquency_bucket,
            {score_sql} AS intelligence_score_sql
        FROM applications a
        {where_sql}
        ORDER BY intelligence_score_sql DESC,
            {days_sql} DESC,
            COALESCE(a.outstanding_balance, 0) DESC,
            a.id DESC
        LIMIT ? OFFSET ?
        """,
        (*params, limit, offset),
    )
    return cursor.fetchall()


def fetch_recovery_summary_metrics(cursor, range_clause: str, range_params: list) -> dict:
    predicate = collections_queue_predicate("a")
    cursor.execute(
        f"""
        SELECT
            COUNT(*) AS queue_total,
            SUM(CASE WHEN collections_status = 'resolved' THEN 1 ELSE 0 END) AS resolved_in_queue,
            SUM(CASE WHEN collections_status = 'write_off_recommended' THEN 1 ELSE 0 END) AS writeoff_count,
            SUM(CASE WHEN collections_status = 'promise_to_pay' THEN 1 ELSE 0 END) AS promise_to_pay_count,
            SUM(CASE WHEN collections_status IN ('legal_escalation', 'escalated_review') THEN 1 ELSE 0 END) AS escalated_count,
            SUM(COALESCE(outstanding_balance, 0)) AS total_exposure,
            SUM(CASE WHEN collections_status = 'resolved' THEN COALESCE(outstanding_balance, 0) ELSE 0 END) AS resolved_exposure,
            SUM(CASE WHEN collections_status = 'write_off_recommended' THEN COALESCE(outstanding_balance, 0) ELSE 0 END) AS writeoff_exposure
        FROM applications a
        WHERE {predicate}
        """
    )
    row = cursor.fetchone()
    queue_total = row["queue_total"] or 0
    resolved = row["resolved_in_queue"] or 0
    recovery_rate = round((resolved / queue_total) * 100, 1) if queue_total else 0.0

    cursor.execute(
        f"""
        SELECT COUNT(*) FROM collections_history ch
        WHERE ch.collections_status = 'resolved'{range_clause}
        """,
        range_params,
    )
    period_resolutions = cursor.fetchone()[0] or 0

    return {
        "queue_total": queue_total,
        "resolved_count": resolved,
        "writeoff_count": row["writeoff_count"] or 0,
        "promise_to_pay_count": row["promise_to_pay_count"] or 0,
        "escalated_count": row["escalated_count"] or 0,
        "recovery_rate_pct": recovery_rate,
        "period_resolutions": period_resolutions,
        "total_exposure": round(row["total_exposure"] or 0, 2),
        "resolved_exposure": round(row["resolved_exposure"] or 0, 2),
        "writeoff_exposure": round(row["writeoff_exposure"] or 0, 2),
    }


def fetch_collections_resolution_trend(cursor, range_clause: str, range_params: list) -> list[dict]:
    cursor.execute(
        f"""
        SELECT date(ch.created_at) AS day_label,
               COUNT(*) AS count
        FROM collections_history ch
        WHERE ch.collections_status = 'resolved'
          AND ch.created_at IS NOT NULL AND ch.created_at != ''{range_clause}
        GROUP BY day_label
        ORDER BY day_label ASC
        LIMIT 90
        """,
        range_params,
    )
    return [{"label": row["day_label"], "count": row["count"]} for row in cursor.fetchall()]


def fetch_escalation_distribution(cursor) -> list[dict]:
    predicate = collections_queue_predicate("a")
    cursor.execute(
        f"""
        SELECT collections_status AS bucket, COUNT(*) AS count
        FROM applications a
        WHERE {predicate}
          AND collections_status IN (
              'escalated_review', 'legal_escalation', 'write_off_recommended'
          )
        GROUP BY collections_status
        ORDER BY count DESC
        """
    )
    from constants.collections import COLLECTIONS_STATUS_LABELS

    return [
        {
            "label": COLLECTIONS_STATUS_LABELS.get(row["bucket"], row["bucket"]),
            "bucket": row["bucket"],
            "count": row["count"],
        }
        for row in cursor.fetchall()
    ]


def fetch_officer_recovery_performance(cursor) -> list[dict]:
    predicate = collections_queue_predicate("a")
    cursor.execute(
        f"""
        SELECT
            CASE
                WHEN collections_assigned_to IS NULL OR TRIM(collections_assigned_to) = ''
                THEN 'Unassigned'
                ELSE collections_assigned_to
            END AS officer,
            COUNT(*) AS active_cases,
            SUM(CASE WHEN collections_status = 'resolved' THEN 1 ELSE 0 END) AS resolved_cases,
            SUM(CASE WHEN collections_status IN ('legal_escalation', 'write_off_recommended') THEN 1 ELSE 0 END) AS escalated_cases,
            SUM(COALESCE(outstanding_balance, 0)) AS exposure
        FROM applications a
        WHERE {predicate}
        GROUP BY officer
        ORDER BY resolved_cases DESC, exposure DESC
        LIMIT 15
        """
    )
    rows = []
    for row in cursor.fetchall():
        active = row["active_cases"] or 0
        resolved = row["resolved_cases"] or 0
        rows.append(
            {
                "officer": row["officer"],
                "active_cases": active,
                "resolved_cases": resolved,
                "escalated_cases": row["escalated_cases"] or 0,
                "exposure": round(row["exposure"] or 0, 2),
                "recovery_rate_pct": round((resolved / active) * 100, 1) if active else 0.0,
            }
        )
    return rows


def fetch_recovery_outcome_distribution(cursor) -> list[dict]:
    predicate = collections_queue_predicate("a")
    from constants.collections import COLLECTIONS_STATUS_LABELS

    cursor.execute(
        f"""
        SELECT collections_status AS bucket, COUNT(*) AS count,
               SUM(COALESCE(outstanding_balance, 0)) AS exposure
        FROM applications a
        WHERE {predicate}
        GROUP BY collections_status
        ORDER BY count DESC
        """
    )
    rows = cursor.fetchall()
    total = sum(row["count"] for row in rows) or 1
    return [
        {
            "label": COLLECTIONS_STATUS_LABELS.get(row["bucket"], row["bucket"]),
            "bucket": row["bucket"],
            "count": row["count"],
            "exposure": round(row["exposure"] or 0, 2),
            "share": round((row["count"] / total) * 100, 1),
        }
        for row in cursor.fetchall()
    ]


def fetch_repayment_recovery_velocity(cursor) -> dict:
    cursor.execute(
        """
        SELECT
            COUNT(*) AS payment_count,
            COALESCE(SUM(payment_amount), 0) AS total_recovered,
            COALESCE(AVG(payment_amount), 0) AS avg_payment
        FROM repayments
        WHERE payment_date IS NOT NULL AND payment_date != ''
          AND date(payment_date) >= date('now', '-30 days')
        """
    )
    row = cursor.fetchone()
    return {
        "payment_count_30d": row["payment_count"] or 0,
        "total_recovered_30d": round(row["total_recovered"] or 0, 2),
        "avg_payment_30d": round(row["avg_payment"] or 0, 2),
    }


def count_stale_critical_risk_accounts(cursor, stale_days: int) -> int:
    predicate = collections_queue_predicate("a")
    cursor.execute(
        f"""
        SELECT COUNT(*) FROM applications a
        WHERE {predicate}
          AND collections_risk_level IN ('critical', 'legal')
          AND collections_status NOT IN ('resolved', 'not_in_collections')
          AND (
              collections_last_contact_at IS NULL
              OR TRIM(collections_last_contact_at) = ''
              OR date(collections_last_contact_at) < date('now', '-{stale_days} days')
          )
        """
    )
    return cursor.fetchone()[0] or 0


def count_unresolved_legal_escalations(cursor) -> int:
    predicate = collections_queue_predicate("a")
    cursor.execute(
        f"""
        SELECT COUNT(*) FROM applications a
        WHERE {predicate}
          AND collections_status = 'legal_escalation'
          AND loan_lifecycle_status NOT IN ('completed', 'written_off')
        """
    )
    return cursor.fetchone()[0] or 0


def count_writeoff_recommendations_recent(cursor, days: int = 30) -> int:
    cursor.execute(
        f"""
        SELECT COUNT(*) FROM collections_history
        WHERE collections_status = 'write_off_recommended'
          AND created_at IS NOT NULL
          AND date(created_at) >= date('now', '-{days} days')
        """
    )
    return cursor.fetchone()[0] or 0


def iter_collections_recovery_summary_export(cursor, *, batch_size: int = 500):
    predicate = collections_queue_predicate("a")
    days_sql = _delinquency_days_sql("a")
    score_sql = intelligence_score_sql("a")
    offset = 0
    while True:
        cursor.execute(
            f"""
            SELECT
                a.id,
                a.business_name,
                a.loan_account_number,
                a.collections_status,
                a.collections_assigned_to,
                {days_sql} AS days_overdue,
                COALESCE(a.outstanding_balance, 0) AS outstanding_balance,
                {score_sql} AS intelligence_score
            FROM applications a
            WHERE {predicate}
            ORDER BY intelligence_score DESC, a.id DESC
            LIMIT ? OFFSET ?
            """,
            (batch_size, offset),
        )
        rows = cursor.fetchall()
        if not rows:
            break
        for row in rows:
            from services.collections_priority import raw_score_to_tier

            item = dict(row)
            item["intelligence_tier"] = raw_score_to_tier(int(item["intelligence_score"]))
            yield item
        if len(rows) < batch_size:
            break
        offset += batch_size


def fetch_escalation_report_rows(cursor, limit: int) -> list[dict]:
    predicate = collections_queue_predicate("a")
    days_sql = _delinquency_days_sql("a")
    cursor.execute(
        f"""
        SELECT
            a.id,
            a.business_name,
            a.loan_account_number,
            a.collections_status,
            a.collections_priority,
            a.collections_assigned_to,
            a.collections_risk_level,
            {days_sql} AS days_overdue,
            COALESCE(a.outstanding_balance, 0) AS outstanding_balance,
            a.flagged_fraud
        FROM applications a
        WHERE {predicate}
          AND a.collections_status IN (
              'escalated_review', 'legal_escalation', 'write_off_recommended'
          )
        ORDER BY {days_sql} DESC, outstanding_balance DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(row) for row in cursor.fetchall()]
