"""Promise-to-pay analytics (Phase F3)."""

from __future__ import annotations

from services.analytics_query import analytics_datetime_clause
from repositories.promises import (
    fetch_commitment_aging_distribution,
    fetch_officer_promise_performance,
    fetch_repayment_conversion_rows,
)


def build_promise_analytics_package(cursor, range_key: str) -> dict:
    range_clause, range_params = analytics_datetime_clause(range_key, "created_at")
    if range_clause:
        period_clause = range_clause.replace("created_at", "rp.created_at")
    else:
        period_clause = ""
        range_params = []

    cursor.execute(
        f"""
        SELECT
            COUNT(*) AS total_promises,
            SUM(CASE WHEN promise_status = 'fulfilled' THEN 1 ELSE 0 END) AS fulfilled,
            SUM(CASE WHEN promise_status = 'broken' THEN 1 ELSE 0 END) AS broken,
            SUM(CASE WHEN promise_status = 'active' THEN 1 ELSE 0 END) AS active,
            SUM(CASE WHEN promise_status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled,
            SUM(CASE WHEN promise_status = 'expired' THEN 1 ELSE 0 END) AS expired
        FROM recovery_promises
        """
    )
    totals = cursor.fetchone()
    total = totals["total_promises"] or 0
    fulfilled = totals["fulfilled"] or 0
    broken = totals["broken"] or 0
    terminal = fulfilled + broken + (totals["cancelled"] or 0) + (totals["expired"] or 0)

    cursor.execute(
        f"""
        SELECT COUNT(*) FROM recovery_promises rp
        WHERE rp.created_at IS NOT NULL AND rp.created_at != ''{period_clause}
        """,
        range_params,
    )
    period_created = cursor.fetchone()[0] or 0

    fulfillment_rate = round((fulfilled / terminal) * 100, 1) if terminal else 0.0
    broken_rate = round((broken / terminal) * 100, 1) if terminal else 0.0

    cursor.execute(
        """
        SELECT COUNT(DISTINCT rp.id) FROM recovery_promises rp
        WHERE rp.promise_status = 'fulfilled'
          AND EXISTS (
              SELECT 1 FROM repayments r
              WHERE r.application_id = rp.application_id
                AND date(r.payment_date) >= date(rp.promise_date)
                AND r.payment_amount > 0
          )
        """
    )
    conversion_count = cursor.fetchone()[0] or 0
    conversion_rate = round((conversion_count / fulfilled) * 100, 1) if fulfilled else 0.0

    metrics = {
        "total_promises": total,
        "active_promises": totals["active"] or 0,
        "fulfilled_count": fulfilled,
        "broken_count": broken,
        "fulfillment_rate_pct": fulfillment_rate,
        "broken_rate_pct": broken_rate,
        "period_created": period_created,
        "repayment_after_promise_count": conversion_count,
        "repayment_conversion_pct": conversion_rate,
    }

    return {
        "metrics": metrics,
        "officer_performance": fetch_officer_promise_performance(cursor),
        "commitment_aging": fetch_commitment_aging_distribution(cursor),
        "range_key": range_key,
    }


def promise_analytics_insights(package: dict) -> list[str]:
    m = package.get("metrics", {})
    insights: list[str] = []
    if m.get("active_promises"):
        insights.append(f"{m['active_promises']} active repayment promises in portfolio.")
    if m.get("fulfillment_rate_pct") is not None and m.get("total_promises"):
        insights.append(f"Promise fulfillment rate: {m['fulfillment_rate_pct']}% of closed commitments.")
    if m.get("broken_rate_pct") and m.get("broken_count"):
        insights.append(f"{m['broken_count']} broken promises ({m['broken_rate_pct']}% of closed).")
    if m.get("repayment_conversion_pct") and m.get("fulfilled_count"):
        insights.append(
            f"{m['repayment_conversion_pct']}% of fulfilled promises had repayments on or after promise date."
        )
    return insights[:5]
