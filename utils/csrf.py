import hmac
import secrets

from flask import session

def ensure_session_csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def validate_csrf(form_token: str) -> bool:
    session_token = session.get("csrf_token")
    if not session_token or not form_token:
        return False
    return hmac.compare_digest(session_token, form_token)
