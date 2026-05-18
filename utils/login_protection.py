"""Lightweight in-memory login attempt tracking (Phase D1)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from flask import request

from constants.ops import DEFAULT_LOGIN_LOCKOUT_SECONDS, DEFAULT_LOGIN_MAX_ATTEMPTS
from utils.env import get_int_env
from utils.ops_logging import log_auth_warning


@dataclass
class LoginAttemptState:
    failures: int = 0
    locked_until: float = 0.0


_lock = threading.Lock()
_states: dict[str, LoginAttemptState] = {}


def _max_attempts() -> int:
    return max(1, get_int_env("LOGIN_MAX_ATTEMPTS", DEFAULT_LOGIN_MAX_ATTEMPTS))


def _lockout_seconds() -> int:
    return max(60, get_int_env("LOGIN_LOCKOUT_SECONDS", DEFAULT_LOGIN_LOCKOUT_SECONDS))


def login_attempt_key(identity: str) -> str:
    remote = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    normalized_identity = (identity or "").strip().lower() or "unknown"
    return f"{remote}:{normalized_identity}"


def is_login_locked(key: str) -> bool:
    now = time.time()
    with _lock:
        state = _states.get(key)
        if state is None:
            return False
        if state.locked_until and state.locked_until > now:
            return True
        if state.locked_until and state.locked_until <= now:
            state.failures = 0
            state.locked_until = 0.0
        return False


def register_failed_login(key: str, *, identity: str) -> bool:
    """Record a failed attempt. Returns True when the key becomes locked."""
    now = time.time()
    with _lock:
        state = _states.setdefault(key, LoginAttemptState())
        state.failures += 1
        if state.failures >= _max_attempts():
            state.locked_until = now + _lockout_seconds()
            locked = True
        else:
            locked = False

    failures = state.failures
    if locked:
        log_auth_warning(
            "auth.login.locked",
            "Login temporarily locked after repeated failures",
            identity=identity,
            client_key=key,
            lockout_seconds=_lockout_seconds(),
            failure_count=failures,
        )
    else:
        log_auth_warning(
            "auth.login.failed",
            "Failed login attempt",
            identity=identity,
            client_key=key,
            failure_count=failures,
        )
    return locked


def register_successful_login(key: str) -> None:
    with _lock:
        _states.pop(key, None)
