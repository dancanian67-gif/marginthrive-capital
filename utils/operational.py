"""Shared operational route helpers (Phase D1–E3)."""

import time

from flask import g, request

from constants.governance import EXPORT_TYPE_METADATA
from utils.auth import get_request_actor
from utils.governance import log_sensitive_export
from utils.ops_logging import log_export_event
from utils.resilience import warn_large_export


def current_operational_actor() -> str:
    return getattr(g, "admin_actor", None) or get_request_actor()


def _export_metadata(export_type: str) -> dict:
    if export_type in EXPORT_TYPE_METADATA:
        return EXPORT_TYPE_METADATA[export_type]
    prefixed = f"report_{export_type}"
    return EXPORT_TYPE_METADATA.get(
        prefixed,
        {"sensitivity": "standard", "governance_tag": None},
    )


def log_admin_export(
    export_type: str,
    *,
    row_count: int | None = None,
    filename: str | None = None,
    range_key: str | None = None,
    filters: dict | None = None,
    **fields,
) -> None:
    operator = getattr(g, "operator", None)
    actor = current_operational_actor()
    role = (operator or {}).get("role", "")
    meta = _export_metadata(export_type)
    sensitivity = meta["sensitivity"]

    log_export_event(
        "Operational export generated",
        export_type=export_type,
        actor=actor,
        operator_role=role,
        operator_id=(operator or {}).get("id"),
        path=request.path,
        sensitivity=sensitivity,
        range_key=range_key or fields.get("range_key", ""),
        filters=filters or {},
        row_count=row_count,
        **fields,
    )

    if sensitivity in ("elevated", "governance"):
        log_sensitive_export(
            export_type=export_type,
            actor=actor,
            role=role,
            sensitivity=sensitivity,
            row_count=row_count,
            filename=filename or fields.get("filename", ""),
            range_key=range_key or fields.get("range_key", ""),
            filters=filters or {},
        )

    if row_count is not None:
        warn_large_export(
            row_count,
            export_type=export_type,
            filename=filename or fields.get("filename", ""),
        )


def export_timer_start() -> float:
    return time.perf_counter()
