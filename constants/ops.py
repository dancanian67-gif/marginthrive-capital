"""Operational resilience constants (Phase D1, E2)."""

DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOGIN_MAX_ATTEMPTS = 5
DEFAULT_LOGIN_LOCKOUT_SECONDS = 900
MIN_PRODUCTION_SECRET_KEY_LENGTH = 32

REQUIRED_DATABASE_TABLES = (
    "applications",
    "workflow_history",
    "underwriting_decisions",
    "repayments",
    "loan_account_history",
    "officers",
    "operators",
    "collections_history",
    "recovery_promises",
    "recovery_promise_history",
    "operational_events",
    "operator_notifications",
)

# Phase G1 — notification operational warning thresholds
NOTIFICATION_CRITICAL_UNRESOLVED_WARN = 15
NOTIFICATION_BACKLOG_WARN = 200
NOTIFICATION_GOVERNANCE_SPIKE_WARN = 25

# Phase F3 — promise operational warning thresholds
PROMISE_BROKEN_RATE_WARN_PCT = 40.0
PROMISE_AGING_UNRESOLVED_WARN = 10
PROMISE_REPEAT_CYCLE_WARN = 3

# Phase E2 — export and analytics thresholds (warnings only; exports are not blocked)
EXPORT_WARN_ROW_THRESHOLD = 5000
EXPORT_SLOW_SECONDS = 5.0
ANALYTICS_OVERSIZED_RANGE_KEYS = frozenset({"all", "90d"})

# Phase F2 — collections operational warning thresholds (log-only)
COLLECTIONS_QUEUE_WARN_SIZE = 150
COLLECTIONS_CRITICAL_QUEUE_WARN = 25
COLLECTIONS_STALE_FOLLOW_UP_DAYS = 14
COLLECTIONS_STALE_CONTACT_DAYS = 21
COLLECTIONS_WRITEOFF_SPIKE_WARN = 5
COLLECTIONS_DELINQUENCY_GROWTH_WARN_RATIO = 0.25
PROMISE_CONVERSION_DROP_WARN_PCT = 20.0

# SQLite connection tuning
SQLITE_BUSY_TIMEOUT_MS = 5000
SQLITE_ENABLE_WAL = True

# Startup directory expectations (created when missing if writable parent exists)
STARTUP_OPTIONAL_DIRS = ("backups",)
DEFAULT_BACKUP_DIR = "backups"

# Performance indexes created by init_db (used for startup verification)
PERFORMANCE_INDEX_NAMES = (
    "idx_applications_created_at",
    "idx_applications_status",
    "idx_applications_risk_level",
    "idx_applications_assigned_officer",
    "idx_applications_underwriting_status",
    "idx_applications_loan_lifecycle_status",
    "idx_applications_reviewed_at",
    "idx_workflow_history_application",
    "idx_workflow_history_batch",
    "idx_workflow_history_created_at",
    "idx_underwriting_decisions_application",
    "idx_underwriting_decisions_reviewed_at",
    "idx_repayments_application",
    "idx_repayments_payment_date",
    "idx_loan_account_history_application",
    "idx_loan_account_history_created_at",
    "idx_operators_username",
    "idx_operators_active",
)
