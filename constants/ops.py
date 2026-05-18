"""Operational resilience constants (Phase D1)."""

DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOGIN_MAX_ATTEMPTS = 5
DEFAULT_LOGIN_LOCKOUT_SECONDS = 900
MIN_PRODUCTION_SECRET_KEY_LENGTH = 32

REQUIRED_DATABASE_TABLES = (
    "applications",
    "workflow_history",
    "underwriting_decisions",
    "officers",
    "operators",
)
