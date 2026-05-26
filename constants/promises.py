"""Recovery promise / commitment constants (Phase F3)."""

PROMISE_STATUSES = ("active", "fulfilled", "broken", "cancelled", "expired")

PROMISE_STATUS_LABELS = {
    "active": "Active",
    "fulfilled": "Fulfilled",
    "broken": "Broken",
    "cancelled": "Cancelled",
    "expired": "Expired",
}

DEFAULT_PROMISE_STATUS = "active"

TERMINAL_PROMISE_STATUSES = frozenset({"fulfilled", "broken", "cancelled", "expired"})

PROMISE_STATUSES_REQUIRING_CONTEXT = frozenset({"broken", "cancelled"})

PROMISE_CRITICAL_STATUSES = frozenset({"broken"})

PROMISE_FIELD_ACTION_TYPES = {
    "promise_status": "promise_status_change",
    "promise_amount": "promise_amount_change",
    "promise_date": "promise_date_change",
    "commitment_notes": "promise_notes_update",
}

PROMISE_AUDIT_FIELDS = (
    "promise_amount",
    "promise_date",
    "promise_status",
    "commitment_notes",
)

MAX_PROMISE_NOTES_LENGTH = 3000
MAX_PROMISE_AMOUNT = 50_000_000.0
PROMISE_HISTORY_LIMIT = 50
PROMISE_LIST_FILTER_KEYS = (
    "promise_filter",
)

# Queue filter presets (additive to collections list)
PROMISE_QUEUE_FILTERS = frozenset(
    {
        "overdue_promises",
        "broken_commitments",
        "promises_due_today",
        "promises_due_week",
    }
)

PROMISE_QUEUE_FILTER_LABELS = {
    "overdue_promises": "Overdue promises",
    "broken_commitments": "Broken commitments (recent)",
    "promises_due_today": "Promises due today",
    "promises_due_week": "Promises due this week",
}
