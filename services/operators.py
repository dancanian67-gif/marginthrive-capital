from werkzeug.security import generate_password_hash

from constants.operators import (
    DEFAULT_OPERATOR_ROLE,
    MAX_OPERATOR_DISPLAY_NAME_LENGTH,
    MAX_OPERATOR_EMAIL_LENGTH,
    MAX_OPERATOR_USERNAME_LENGTH,
    MIN_OPERATOR_PASSWORD_LENGTH,
    OPERATOR_EMAIL_PATTERN,
    OPERATOR_USERNAME_PATTERN,
    is_valid_operator_role,
)
from repositories.database import get_db_connection
from repositories.operators import (
    count_active_administrators,
    create_operator_record,
    email_exists,
    set_operator_active,
    update_operator_role,
    username_exists,
)


def normalize_username(raw: str) -> str:
    return (raw or "").strip()


def normalize_email(raw: str) -> str:
    return (raw or "").strip().lower()


def normalize_display_name(raw: str, fallback_username: str) -> str:
    value = " ".join((raw or "").split())
    if not value:
        return fallback_username[:MAX_OPERATOR_DISPLAY_NAME_LENGTH]
    return value[:MAX_OPERATOR_DISPLAY_NAME_LENGTH]


def validate_new_operator_payload(data) -> tuple[dict | None, str | None]:
    username = normalize_username(data.get("username", ""))
    email = normalize_email(data.get("email", ""))
    display_name = normalize_display_name(data.get("display_name", ""), username)
    role = (data.get("role") or DEFAULT_OPERATOR_ROLE).strip()
    password = data.get("password") or ""
    password_confirm = data.get("password_confirm") or ""

    if not username or len(username) > MAX_OPERATOR_USERNAME_LENGTH:
        return None, "Enter a username between 3 and 64 characters."
    if not OPERATOR_USERNAME_PATTERN.match(username):
        return None, "Username may only contain letters, numbers, dots, underscores, and hyphens."
    if not email or len(email) > MAX_OPERATOR_EMAIL_LENGTH:
        return None, "Enter a valid email address."
    if not OPERATOR_EMAIL_PATTERN.match(email):
        return None, "Enter a valid email address."
    if not is_valid_operator_role(role):
        return None, "Select a valid operational role."
    if len(password) < MIN_OPERATOR_PASSWORD_LENGTH:
        return None, f"Password must be at least {MIN_OPERATOR_PASSWORD_LENGTH} characters."
    if password != password_confirm:
        return None, "Password confirmation does not match."

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if username_exists(cursor, username):
            return None, "That username is already in use."
        if email_exists(cursor, email):
            return None, "That email is already in use."
    finally:
        conn.close()

    return {
        "username": username,
        "email": email,
        "display_name": display_name,
        "role": role,
        "password_hash": generate_password_hash(password),
    }, None


def create_operator(data) -> tuple[int | None, str | None]:
    payload, error = validate_new_operator_payload(data)
    if error:
        return None, error

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        operator_id = create_operator_record(cursor, **payload)
        conn.commit()
        return operator_id, None
    finally:
        conn.close()


def change_operator_role(operator_id: int, role: str, acting_operator_id: int) -> str | None:
    if not is_valid_operator_role(role):
        return "Select a valid operational role."
    if operator_id == acting_operator_id and role != "administrator":
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            if count_active_administrators(cursor, exclude_id=operator_id) < 1:
                return "You cannot remove your own administrator access while you are the only active administrator."
        finally:
            conn.close()

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if not update_operator_role(cursor, operator_id, role):
            return "Operator not found."
        conn.commit()
        return None
    finally:
        conn.close()


def set_operator_status(
    operator_id: int,
    *,
    active: bool,
    acting_operator_id: int,
) -> str | None:
    if operator_id == acting_operator_id and not active:
        return "You cannot deactivate your own operator account."

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if not active:
            cursor.execute(
                "SELECT role FROM operators WHERE id = ?",
                (operator_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return "Operator not found."
            if row["role"] == "administrator" and count_active_administrators(cursor, exclude_id=operator_id) < 1:
                return "At least one active administrator must remain."

        if not set_operator_active(cursor, operator_id, active):
            return "Operator not found."
        conn.commit()
        return None
    finally:
        conn.close()
