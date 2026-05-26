"""Promise operational warnings (Phase F3) — log-only."""

from __future__ import annotations

from constants.ops import (
    PROMISE_AGING_UNRESOLVED_WARN,
    PROMISE_BROKEN_RATE_WARN_PCT,
    PROMISE_REPEAT_CYCLE_WARN,
)
from repositories.promises import fetch_unresolved_expired_active
from utils.ops_logging import log_operational_warning


def warn_promise_broken_rate(cursor) -> None:
    cursor.execute(
        """
        SELECT
            SUM(CASE WHEN promise_status = 'broken' THEN 1 ELSE 0 END) AS broken,
            SUM(CASE WHEN promise_status IN ('fulfilled', 'broken', 'cancelled', 'expired') THEN 1 ELSE 0 END) AS closed
        FROM recovery_promises
        """
    )
    row = cursor.fetchone()
    closed = row["closed"] or 0
    broken = row["broken"] or 0
    if closed and (broken / closed) * 100 >= PROMISE_BROKEN_RATE_WARN_PCT:
        log_operational_warning(
            "Elevated broken promise rate",
            broken_count=broken,
            closed_count=closed,
            broken_rate_pct=round((broken / closed) * 100, 1),
            threshold_pct=PROMISE_BROKEN_RATE_WARN_PCT,
        )


def warn_aging_unresolved_commitments(cursor) -> None:
    count = fetch_unresolved_expired_active(cursor)
    if count >= PROMISE_AGING_UNRESOLVED_WARN:
        log_operational_warning(
            "Aging active promises past commitment date",
            stale_active_count=count,
            threshold=PROMISE_AGING_UNRESOLVED_WARN,
        )


def warn_repeated_promise_cycles(cursor) -> None:
    cursor.execute(
        """
        SELECT application_id, COUNT(*) AS cycles
        FROM recovery_promises
        WHERE promise_status = 'broken'
        GROUP BY application_id
        HAVING cycles >= ?
        """,
        (PROMISE_REPEAT_CYCLE_WARN,),
    )
    rows = cursor.fetchall()
    if rows:
        log_operational_warning(
            "Accounts with repeated broken promise cycles",
            account_count=len(rows),
            min_cycles=PROMISE_REPEAT_CYCLE_WARN,
        )


def warn_low_repayment_conversion(cursor) -> None:
    cursor.execute(
        """
        SELECT COUNT(*) FROM recovery_promises WHERE promise_status = 'fulfilled'
        """
    )
    fulfilled = cursor.fetchone()[0] or 0
    if not fulfilled:
        return
    cursor.execute(
        """
        SELECT COUNT(DISTINCT rp.id) FROM recovery_promises rp
        WHERE rp.promise_status = 'fulfilled'
          AND EXISTS (
              SELECT 1 FROM repayments r
              WHERE r.application_id = rp.application_id
                AND date(r.payment_date) >= date(rp.promise_date)
          )
        """
    )
    with_repayment = cursor.fetchone()[0] or 0
    rate = (with_repayment / fulfilled) * 100
    if fulfilled >= 5 and rate < 20:
        log_operational_warning(
            "Low repayment-after-promise conversion rate",
            conversion_pct=round(rate, 1),
            fulfilled_count=fulfilled,
            with_repayment=with_repayment,
        )


def run_promise_operational_warnings(cursor) -> None:
    warn_promise_broken_rate(cursor)
    warn_aging_unresolved_commitments(cursor)
    warn_repeated_promise_cycles(cursor)
    warn_low_repayment_conversion(cursor)
