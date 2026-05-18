import os

from constants.ops import MIN_PRODUCTION_SECRET_KEY_LENGTH


def is_development() -> bool:
    env_value = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower()
    return env_value in {"dev", "development", "local"}


def is_production() -> bool:
    env_value = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower()
    return env_value in {"prod", "production"}


def get_bool_env(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def get_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def validate_environment(*, strict: bool = False) -> list[str]:
    """Return human-readable configuration issues. Raises when strict and errors exist."""
    issues: list[str] = []
    secret_key = os.getenv("SECRET_KEY", "")

    if is_production():
        if not secret_key or secret_key == "dev-only-secret-key-change-me":
            issues.append("SECRET_KEY must be set to a strong random value in production.")
        elif len(secret_key) < MIN_PRODUCTION_SECRET_KEY_LENGTH:
            issues.append(
                f"SECRET_KEY should be at least {MIN_PRODUCTION_SECRET_KEY_LENGTH} characters in production."
            )
        if get_bool_env("FLASK_DEBUG", default=False):
            issues.append("FLASK_DEBUG must be disabled in production.")
    elif not secret_key:
        issues.append("SECRET_KEY is not set; using development fallback.")

    database_path = os.getenv("DATABASE_PATH", "database.db")
    database_dir = os.path.dirname(os.path.abspath(database_path)) or "."
    if not os.path.isdir(database_dir):
        issues.append(f"Database directory does not exist: {database_dir}")
    elif not os.access(database_dir, os.W_OK):
        issues.append(f"Database directory is not writable: {database_dir}")

    if strict and issues:
        raise RuntimeError("Environment validation failed:\n- " + "\n- ".join(issues))
    return issues
