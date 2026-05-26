import os
import re

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ALLOWED_PRODUCTS = {"MarginPro", "HustleBoost", "QuickBridge"}

RENDER_PERSISTENT_DATA_DIR = "/var/data"


def resolve_database_path() -> str:
    """Resolve SQLite path: explicit env, Render disk, or local default."""
    explicit = (os.getenv("DATABASE_PATH") or "").strip()
    if explicit:
        return explicit

    if os.getenv("RENDER"):
        persistent_dir = os.getenv("RENDER_DISK_PATH", RENDER_PERSISTENT_DATA_DIR).strip()
        if persistent_dir and os.path.isdir(persistent_dir):
            return os.path.join(persistent_dir, "database.db")
        data_dir = os.path.join(os.getcwd(), "data")
        return os.path.join(data_dir, "database.db")

    return "database.db"


DATABASE_PATH = resolve_database_path()
