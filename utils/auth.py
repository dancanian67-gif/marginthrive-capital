import base64
import hmac
import os
from functools import wraps

from flask import Response, g, request

def _parse_basic_auth_credentials(auth_header: str | None) -> tuple[str, str] | None:
    if not auth_header or not auth_header.startswith("Basic "):
        return None

    try:
        encoded_credentials = auth_header.split(" ", 1)[1]
        decoded = base64.b64decode(encoded_credentials).decode("utf-8")
        username, password = decoded.split(":", 1)
        return username, password
    except Exception:
        return None


def _check_admin_auth(auth_header: str | None) -> bool:
    credentials = _parse_basic_auth_credentials(auth_header)
    if not credentials:
        return False

    expected_username = os.getenv("ADMIN_USERNAME")
    expected_password = os.getenv("ADMIN_PASSWORD")
    if not expected_username or not expected_password:
        return False

    username, password = credentials
    return hmac.compare_digest(username, expected_username) and hmac.compare_digest(password, expected_password)


def get_request_actor() -> str:
    configured = os.getenv("ADMIN_USERNAME")
    credentials = _parse_basic_auth_credentials(request.headers.get("Authorization"))
    if credentials:
        username, _password = credentials
        if configured and hmac.compare_digest(username, configured):
            return username
        return username
    return configured or "admin"


def require_admin_auth(route_fn):
    @wraps(route_fn)
    def wrapper(*args, **kwargs):
        if not (os.getenv("ADMIN_USERNAME") and os.getenv("ADMIN_PASSWORD")):
            return Response("Admin credentials are not configured.", status=503)

        if not _check_admin_auth(request.headers.get("Authorization")):
            return Response(
                "Authentication required",
                401,
                {"WWW-Authenticate": 'Basic realm="Admin Dashboard"'},
            )

        g.admin_actor = get_request_actor()
        return route_fn(*args, **kwargs)

    return wrapper
