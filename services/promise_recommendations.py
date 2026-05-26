"""Recovery promise operator recommendations (Phase F3) — guidance only."""

from __future__ import annotations

from datetime import date


def _parse_date(raw: str | None) -> date | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def build_promise_recommendations(
    application: dict,
    *,
    active_promise: dict | None,
    broken_count: int = 0,
    fulfilled_count: int = 0,
    repayments_after_promise: float = 0.0,
) -> dict:
    warnings: list[str] = []
    recommendations: list[str] = []

    if active_promise:
        promise_date = _parse_date(active_promise.get("promise_date"))
        amount = float(active_promise.get("promise_amount") or 0)
        if promise_date and promise_date < date.today():
            warnings.append("Active promise date has passed — commitment is overdue.")
            recommendations.append("Contact borrower and mark promise fulfilled, broken, or reschedule.")
        elif promise_date and promise_date == date.today():
            recommendations.append("Promise is due today — confirm payment or update commitment status.")

        if repayments_after_promise >= amount and amount > 0:
            recommendations.append(
                "Repayments meet or exceed promise amount — consider marking promise as fulfilled."
            )

    if broken_count >= 2:
        warnings.append(f"{broken_count} broken promises on record.")
        recommendations.append("Escalate for settlement review or revised recovery plan.")

    if broken_count >= 3:
        recommendations.append("Repeated broken promises — recommend escalated collections review.")

    days_overdue = int(application.get("days_overdue") or 0)
    if days_overdue >= 90 and not active_promise:
        recommendations.append("Chronic delinquency — consider structured promise or legal escalation review.")

    tier = application.get("intelligence_tier", "")
    if tier == "critical" and active_promise:
        recommendations.append("Critical account with active promise — prioritize follow-up today.")

    if fulfilled_count >= 1 and broken_count == 0 and days_overdue <= 30:
        recommendations.append("Prior fulfillment history — strong candidate for renewed commitment.")

    intelligence_score = int(application.get("intelligence_score") or 0)
    if intelligence_score >= 75 and active_promise:
        warnings.append("High intelligence priority with open promise — monitor closely.")

    return {
        "warnings": warnings[:6],
        "recommendations": recommendations[:5],
    }
