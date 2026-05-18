"""Centralized operational error handling (Phase D1)."""

from werkzeug.exceptions import HTTPException

from flask import flash, jsonify, redirect, request, url_for

from utils.ops_logging import log_unexpected_exception

GENERIC_OPERATOR_ERROR = (
    "An unexpected operational error occurred. Please try again. "
    "If the problem continues, contact your platform administrator."
)
GENERIC_PUBLIC_ERROR = "We could not complete that request right now. Please try again shortly."


def _is_admin_request() -> bool:
    return request.path.startswith("/admin")


def _wants_json_response() -> bool:
    accept = request.headers.get("Accept", "")
    return "application/json" in accept or request.path.startswith("/health")


def register_error_handlers(app) -> None:
    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        if error.code and error.code >= 500:
            log_unexpected_exception("HTTP server error", exc=error)
        message = error.description or GENERIC_OPERATOR_ERROR
        return _handle_operational_error(error, error.code or 500, message)

    @app.errorhandler(Exception)
    def handle_unexpected_exception(error: Exception):
        if isinstance(error, HTTPException):
            return error
        log_unexpected_exception("Unhandled exception", exc=error)
        return _handle_operational_error(
            error,
            500,
            GENERIC_OPERATOR_ERROR,
            public_message=GENERIC_PUBLIC_ERROR,
        )


def _handle_operational_error(error, status_code: int, admin_message: str, *, public_message: str | None = None):
    if _wants_json_response():
        return jsonify({"status": "error", "message": admin_message}), status_code

    if _is_admin_request():
        flash(admin_message, "error")
        return redirect(url_for("admin_overview"))

    message = public_message or GENERIC_PUBLIC_ERROR
    return message, status_code


def flash_operational_error(message: str | None = None) -> None:
    flash(message or GENERIC_OPERATOR_ERROR, "error")
