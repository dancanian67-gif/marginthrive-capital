import logging
import os
import sys
from typing import Any

from utils.env import get_bool_env, is_development

OPS_LOGGER_NAME = "marginthrive.ops"
_CONFIGURED = False


class _OperationalLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "event", "operational")
        base = super().format(record)
        fields = getattr(record, "fields", None)
        if fields:
            field_text = " ".join(f"{key}={value}" for key, value in fields.items())
            return f"{base} event={event} {field_text}"
        return f"{base} event={event}"


def configure_ops_logging() -> logging.Logger:
    global _CONFIGURED
    logger = logging.getLogger(OPS_LOGGER_NAME)
    if _CONFIGURED:
        return logger

    level_name = os.getenv("LOG_LEVEL", "DEBUG" if is_development() else "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(level)
    logger.propagate = False

    formatter = _OperationalLogFormatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    log_file = (os.getenv("LOG_FILE") or "").strip()
    if log_file:
        log_dir = os.path.dirname(os.path.abspath(log_file))
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if not get_bool_env("LOG_TRACE_REQUESTS", default=is_development()):
        logging.getLogger("werkzeug").setLevel(logging.WARNING)

    _CONFIGURED = True
    return logger


def get_ops_logger() -> logging.Logger:
    return configure_ops_logging()


def _log(level: int, event: str, message: str, **fields: Any) -> None:
    logger = get_ops_logger()
    logger.log(level, message, extra={"event": event, "fields": fields or None})


def log_auth_event(event: str, message: str, **fields: Any) -> None:
    _log(logging.INFO, event, message, **fields)


def log_auth_warning(event: str, message: str, **fields: Any) -> None:
    _log(logging.WARNING, event, message, **fields)


def log_export_event(message: str, **fields: Any) -> None:
    _log(logging.INFO, "export.generated", message, **fields)


def log_workflow_failure(message: str, **fields: Any) -> None:
    _log(logging.ERROR, "workflow.update.failed", message, **fields)


def log_governance_event(message: str, *, critical: bool = False, **fields: Any) -> None:
    event = "governance.critical" if critical else "governance.event"
    level = logging.WARNING if critical else logging.INFO
    _log(level, event, message, **fields)


def log_operational_warning(message: str, **fields: Any) -> None:
    _log(logging.WARNING, "operational.warning", message, **fields)


def log_unexpected_exception(message: str, *, exc: BaseException | None = None, **fields: Any) -> None:
    logger = get_ops_logger()
    logger.exception(
        message,
        exc_info=exc,
        extra={"event": "application.exception", "fields": fields or None},
    )


def log_startup(message: str, **fields: Any) -> None:
    _log(logging.INFO, "startup.check", message, **fields)


# ---- Application intake & persistence logging ----

def log_application_submission(message: str, **fields: Any) -> None:
    _log(logging.INFO, "application.submission", message, **fields)


def log_application_submission_rejected(message: str, **fields: Any) -> None:
    _log(logging.WARNING, "application.submission.rejected", message, **fields)


def log_application_persistence_failed(message: str, **fields: Any) -> None:
    _log(logging.ERROR, "application.persistence.failed", message, **fields)


def log_document_upload(message: str, **fields: Any) -> None:
    _log(logging.INFO, "document.upload", message, **fields)


def log_document_upload_failed(message: str, **fields: Any) -> None:
    _log(logging.ERROR, "document.upload.failed", message, **fields)


# ---- Database commit logging ----

def log_db_commit(message: str, **fields: Any) -> None:
    _log(logging.INFO, "database.commit", message, **fields)


def log_db_commit_failed(message: str, **fields: Any) -> None:
    _log(logging.ERROR, "database.commit.failed", message, **fields)


def log_db_retrieval_count(message: str, **fields: Any) -> None:
    _log(logging.INFO, "database.retrieval.counts", message, **fields)


# ---- Dashboard query logging ----

def log_dashboard_query_result(message: str, **fields: Any) -> None:
    _log(logging.INFO, "dashboard.query.results", message, **fields)


def log_dashboard_query_failed(message: str, **fields: Any) -> None:
    _log(logging.ERROR, "dashboard.query.failed", message, **fields)
