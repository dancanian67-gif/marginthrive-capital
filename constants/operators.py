"""Operator identity, roles, and session constants (Phase C2)."""

import re
from datetime import timedelta

OPERATOR_ROLES = (
    "administrator",
    "review_officer",
    "analyst",
    "operations_manager",
)

OPERATOR_ROLE_LABELS = {
    "administrator": "Administrator",
    "review_officer": "Review officer",
    "analyst": "Analyst",
    "operations_manager": "Operations manager",
}

DEFAULT_OPERATOR_ROLE = "review_officer"
MIN_OPERATOR_PASSWORD_LENGTH = 10
MAX_OPERATOR_USERNAME_LENGTH = 64
MAX_OPERATOR_DISPLAY_NAME_LENGTH = 120
MAX_OPERATOR_EMAIL_LENGTH = 254

OPERATOR_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,64}$")
OPERATOR_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SESSION_OPERATOR_ID = "operator_id"
SESSION_OPERATOR_USERNAME = "operator_username"
SESSION_OPERATOR_ROLE = "operator_role"
SESSION_OPERATOR_DISPLAY_NAME = "operator_display_name"

OPERATOR_SESSION_LIFETIME = timedelta(hours=8)


def role_label(role: str) -> str:
    return OPERATOR_ROLE_LABELS.get(role, role.replace("_", " ").title())


def is_valid_operator_role(role: str) -> bool:
    return role in OPERATOR_ROLES


def can_manage_operators(role: str) -> bool:
    return role == "administrator"
