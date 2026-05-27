import os
import re

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
KENYAN_PHONE_PATTERN = re.compile(r"^(?:07\d{8}|(?:\+?254)7\d{8})$")
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

RENDER_DISK_PATH = "/opt/render/project/src/data"


def resolve_database_path() -> str:
    """Resolve SQLite path: explicit env, Render disk, or local default."""
    explicit = (os.getenv("DATABASE_PATH") or "").strip()
    if explicit:
        return explicit

    if os.getenv("RENDER"):
        return os.path.join(RENDER_DISK_PATH, "database.db")

    return "database.db"


DATABASE_PATH = resolve_database_path()
