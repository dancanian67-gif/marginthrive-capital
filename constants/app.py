import os
import re

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
#
# Public intake product options must match backend validation.
# Keep legacy product values for backwards compatibility.
ALLOWED_PRODUCTS = {
    "Haraka Loan",
    "Daraja Loan",
    "Faida Loan",
    # legacy/internal values (older frontend variants)
    "MarginPro",
    "HustleBoost",
    "QuickBridge",
}

RENDER_PERSISTENT_DATA_DIR = "/var/data"


def resolve_database_path() -> str:
    """Resolve SQLite path: explicit env, Render disk, or local default."""
    explicit = (os.getenv("DATABASE_PATH") or "").strip()
    if explicit:
        return explicit

    if os.getenv("RENDER"):
        persistent_dir = os.getenv("RENDER_DISK_PATH", RENDER_PERSISTENT_DATA_DIR).strip()
        # Always target the Render persistent mount path.
        # SQLite and get_db_connection will create the directory on demand.
        # This avoids multi-worker situations where some workers fall back to
        # ephemeral storage if the mount isn't detected at boot.
        if persistent_dir:
            return os.path.join(persistent_dir, "database.db")
        # Extreme fallback: local relative database file.
        return "database.db"

    return "database.db"


DATABASE_PATH = resolve_database_path()
