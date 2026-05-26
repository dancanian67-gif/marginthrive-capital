"""Collections prioritization engine (Phase F2) — deterministic, SQLite-friendly scoring."""

from __future__ import annotations

import sqlite3
from typing import Any

from constants.collections import (
    INTELLIGENCE_PRIORITY_LABELS,
    INTELLIGENCE_PRIORITY_TIERS,
    INTELLIGENCE_TIER_ORDER,
)
from services.loans import delinquency_context

# Weight caps (sum theoretical max ~100)
_MAX_OVERDUE = 25
_MAX_REPAYMENT_RISK = 15
_MAX_COLLECTIONS_STATUS = 15
_MAX_MANUAL_PRIORITY = 10
_MAX_EXPOSURE = 10
_MAX_MISSED_SIGNAL = 10
_MAX_ESCALATION_HISTORY = 10
_MAX_UNDERWRITING = 5
_MAX_FRAUD = 5
_MAX_VELOCITY_BONUS = 5

_UNDERWRITING_DISTRESS = frozenset({"rejected", "escalated_review", "deferred"})

_STATUS_SCORES = {
    "legal_escalation": 15,
    "write_off_recommended": 14,
    "escalated_review": 12,
    "defaulted": 0,
    "recovery_active": 8,
    "promise_to_pay": 6,
    "payment_plan": 5,
    "in_contact": 4,
    "queued": 3,
    "not_in_collections": 0,
    "resolved": 0,
}

_MANUAL_PRIORITY_SCORES = {"urgent": 10, "high": 7, "normal": 4, "low": 2}

_REPAYMENT_RISK_SCORES = {"critical": 15, "elevated": 10, "watch": 5, "current": 0}


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _overdue_component(days_overdue: int) -> int:
    if days_overdue >= 90:
        return _MAX_OVERDUE
    if days_overdue >= 61:
        return 21
    if days_overdue >= 31:
        return 14
    if days_overdue >= 1:
        return 8
    return 0


def _exposure_component(outstanding: float, issued: float) -> int:
    if outstanding <= 0:
        return 0
    if issued > 0 and outstanding / issued >= 0.9:
        return _MAX_EXPOSURE
    if outstanding >= 50000:
        return 8
    if outstanding >= 10000:
        return 5
    if outstanding >= 1000:
        return 3
    return 1


def _velocity_component(repayment_count: int, days_overdue: int, recent_payment_amount: float) -> int:
    """Higher score when delinquent with no recent recovery momentum."""
    if repayment_count <= 0 and days_overdue > 30:
        return _MAX_VELOCITY_BONUS
    if recent_payment_amount <= 0 and days_overdue > 14:
        return 3
    if recent_payment_amount > 0:
        return 0
    return 1


def compute_raw_priority_score(
    application: sqlite3.Row | dict,
    *,
    repayment_count: int = 0,
    escalation_count: int = 0,
    recent_payment_amount: float = 0.0,
) -> int:
    """Return 0–100 raw intelligence score."""
    data = dict(application) if not isinstance(application, dict) else application
    ctx = delinquency_context(data)
    days_overdue = int(data.get("days_overdue") if data.get("days_overdue") is not None else ctx["days_overdue"])

    score = 0
    score += _overdue_component(days_overdue)
    score += _REPAYMENT_RISK_SCORES.get(data.get("repayment_risk_level") or "current", 0)
    score += _STATUS_SCORES.get(data.get("collections_status") or "not_in_collections", 0)
    score += _MANUAL_PRIORITY_SCORES.get(data.get("collections_priority") or "normal", 0)

    outstanding = _safe_float(data.get("outstanding_balance"))
    issued = _safe_float(data.get("issued_amount"), outstanding or 1.0)
    score += _exposure_component(outstanding, issued)

    if (data.get("missed_payment_observations") or "").strip():
        score += _MAX_MISSED_SIGNAL
    elif ctx["is_delinquent"] and outstanding > 0:
        score += 4

    score += min(_MAX_ESCALATION_HISTORY, escalation_count * 3)

    underwriting = (data.get("underwriting_status") or "").strip()
    if underwriting in _UNDERWRITING_DISTRESS:
        score += _MAX_UNDERWRITING
    elif underwriting == "conditionally_approved":
        score += 2

    if data.get("flagged_fraud"):
        score += _MAX_FRAUD

    coll_risk = data.get("collections_risk_level") or "routine"
    if coll_risk == "legal":
        score += 8
    elif coll_risk == "critical":
        score += 5

    score += _velocity_component(repayment_count, days_overdue, recent_payment_amount)
    return min(100, max(0, score))


def raw_score_to_tier(raw_score: int) -> str:
    if raw_score >= 75:
        return "critical"
    if raw_score >= 50:
        return "elevated"
    if raw_score >= 25:
        return "moderate"
    return "low"


def tier_sort_key(tier: str) -> int:
    return INTELLIGENCE_TIER_ORDER.get(tier, 0)


def attach_priority_intelligence(
    row: dict,
    *,
    repayment_count: int = 0,
    escalation_count: int = 0,
    recent_payment_amount: float = 0.0,
) -> dict:
    """Add intelligence_score, intelligence_tier, intelligence_tier_label to a queue row dict."""
    raw = compute_raw_priority_score(
        row,
        repayment_count=repayment_count,
        escalation_count=escalation_count,
        recent_payment_amount=recent_payment_amount,
    )
    tier = raw_score_to_tier(raw)
    row["intelligence_score"] = raw
    row["intelligence_tier"] = tier
    row["intelligence_tier_label"] = INTELLIGENCE_PRIORITY_LABELS.get(tier, tier)
    return row


def sort_queue_by_intelligence(rows: list[dict]) -> list[dict]:
    """Sort queue rows by intelligence tier/score (desc), preserving stable id tie-break."""
    return sorted(
        rows,
        key=lambda r: (
            tier_sort_key(r.get("intelligence_tier", "low")),
            r.get("intelligence_score", 0),
            int(r.get("days_overdue") or 0),
            _safe_float(r.get("outstanding_balance")),
            int(r.get("id") or 0),
        ),
        reverse=True,
    )


def intelligence_score_sql(alias: str = "a") -> str:
    """Approximate SQL expression for ORDER BY (mirrors primary score drivers)."""
    days = f"""
        CASE
            WHEN {alias}.due_date IS NOT NULL AND TRIM({alias}.due_date) != ''
                 AND COALESCE({alias}.outstanding_balance, 0) > 0
            THEN MAX(0, CAST(julianday('now') - julianday(date({alias}.due_date)) AS INTEGER))
            ELSE 0
        END
    """
    return f"""
        (
            CASE
                WHEN ({days}) >= 90 THEN 25
                WHEN ({days}) >= 61 THEN 21
                WHEN ({days}) >= 31 THEN 14
                WHEN ({days}) >= 1 THEN 8
                ELSE 0
            END
            + CASE COALESCE({alias}.repayment_risk_level, 'current')
                WHEN 'critical' THEN 15 WHEN 'elevated' THEN 10 WHEN 'watch' THEN 5 ELSE 0 END
            + CASE COALESCE({alias}.collections_status, 'not_in_collections')
                WHEN 'legal_escalation' THEN 15
                WHEN 'write_off_recommended' THEN 14
                WHEN 'escalated_review' THEN 12
                WHEN 'recovery_active' THEN 8
                WHEN 'promise_to_pay' THEN 6
                WHEN 'payment_plan' THEN 5
                WHEN 'in_contact' THEN 4
                WHEN 'queued' THEN 3
                ELSE 0 END
            + CASE COALESCE({alias}.collections_priority, 'normal')
                WHEN 'urgent' THEN 10 WHEN 'high' THEN 7 WHEN 'normal' THEN 4 ELSE 2 END
            + CASE WHEN COALESCE({alias}.flagged_fraud, 0) = 1 THEN 5 ELSE 0 END
            + CASE COALESCE({alias}.collections_risk_level, 'routine')
                WHEN 'legal' THEN 8 WHEN 'critical' THEN 5 WHEN 'elevated' THEN 3 ELSE 0 END
        )
    """
