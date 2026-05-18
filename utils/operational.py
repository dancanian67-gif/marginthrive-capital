"""Shared operational route helpers (Phase D1)."""

from flask import g, request

from utils.auth import get_request_actor
from utils.ops_logging import log_export_event


def current_operational_actor() -> str:
    return getattr(g, "admin_actor", None) or get_request_actor()


def log_admin_export(export_type: str, **fields) -> None:
    log_export_event(
        "Operational export generated",
        export_type=export_type,
        actor=current_operational_actor(),
        path=request.path,
        **fields,
    )
