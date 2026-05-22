"""Portfolio intelligence and financial analytics constants (Phase E1)."""

PORTFOLIO_AGING_BUCKETS = (
    "current",
    "1_30_days",
    "31_60_days",
    "61_90_days",
    "90_plus_days",
    "no_due_date",
)

PORTFOLIO_AGING_LABELS = {
    "current": "Current (not past due)",
    "1_30_days": "1–30 days past due",
    "31_60_days": "31–60 days past due",
    "61_90_days": "61–90 days past due",
    "90_plus_days": "90+ days past due",
    "no_due_date": "No due date set",
}

COLLECTIONS_RISK_LEVELS = frozenset({"elevated", "critical"})

ISSUED_LOAN_STATUSES = frozenset(
    {"active", "repaying", "overdue", "completed", "defaulted", "written_off"}
)

DISTRESSED_LOAN_STATUSES = frozenset({"defaulted", "written_off", "overdue"})
