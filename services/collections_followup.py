"""Follow-up scheduling intelligence (Phase F2) — warnings and recommendations only."""

from __future__ import annotations

from datetime import date, timedelta

from constants.ops import COLLECTIONS_STALE_CONTACT_DAYS, COLLECTIONS_STALE_FOLLOW_UP_DAYS


def _parse_date(raw: str | None) -> date | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def follow_up_is_overdue(follow_up_raw: str | None) -> bool:
    follow = _parse_date(follow_up_raw)
    return follow is not None and follow < date.today()


def follow_up_is_due_today(follow_up_raw: str | None) -> bool:
    follow = _parse_date(follow_up_raw)
    return follow is not None and follow == date.today()


def assess_account_followup(application: dict) -> dict:
    """Return follow-up indicators and operator recommendations for one account."""
    warnings: list[str] = []
    recommendations: list[str] = []

    next_follow = application.get("collections_next_follow_up")
    last_contact = application.get("collections_last_contact_at")
    status = application.get("collections_status") or "not_in_collections"
    assigned = (application.get("collections_assigned_to") or "").strip()

    if follow_up_is_overdue(next_follow):
        warnings.append("Follow-up date is overdue.")
        recommendations.append("Contact borrower and schedule a new follow-up date.")
    elif follow_up_is_due_today(next_follow):
        recommendations.append("Follow-up is due today — complete outreach or reschedule.")

    if not next_follow and status not in ("resolved", "not_in_collections"):
        warnings.append("No follow-up date scheduled.")
        recommendations.append("Set a next follow-up date for accountability.")

    last = _parse_date(last_contact)
    if last is None and status in ("in_contact", "queued", "promise_to_pay", "recovery_active"):
        warnings.append("No last-contact date recorded.")
    elif last and (date.today() - last).days >= COLLECTIONS_STALE_CONTACT_DAYS:
        warnings.append(f"No contact recorded in {COLLECTIONS_STALE_CONTACT_DAYS}+ days.")
        recommendations.append("Log contact attempt and update recovery notes.")

    if not assigned and status not in ("resolved", "not_in_collections"):
        warnings.append("Account is unassigned.")
        recommendations.append("Assign a collections officer.")

    if application.get("follow_up_due") and "Follow-up date is overdue" not in warnings:
        warnings.append("Follow-up indicator active.")

    tier = application.get("intelligence_tier", "low")
    if tier == "critical" and status not in ("legal_escalation", "resolved"):
        recommendations.append("Critical intelligence tier — prioritize escalation review.")

    if application.get("flagged_fraud") and status in (
        "legal_escalation",
        "write_off_recommended",
        "escalated_review",
    ):
        warnings.append("Fraud-flagged account in sensitive collections status.")
        recommendations.append("Coordinate with fraud review before recovery closure.")

    return {
        "warnings": warnings[:6],
        "recommendations": recommendations[:5],
        "follow_up_overdue": follow_up_is_overdue(next_follow),
        "follow_up_due_today": follow_up_is_due_today(next_follow),
        "stale_contact": last is not None and (date.today() - last).days >= COLLECTIONS_STALE_CONTACT_DAYS,
        "missing_follow_up": not (next_follow or "").strip(),
    }


def queue_aging_indicator(days_overdue: int) -> str:
    if days_overdue >= 90:
        return "Severely aged (90+ days)"
    if days_overdue >= 61:
        return "Deep delinquency (61–90 days)"
    if days_overdue >= 31:
        return "Aging delinquency (31–60 days)"
    if days_overdue >= 1:
        return "Early delinquency (1–30 days)"
    return "Current / not past due"
