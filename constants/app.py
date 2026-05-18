import os
import re

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ALLOWED_PRODUCTS = {"MarginPro", "HustleBoost", "QuickBridge"}

DATABASE_PATH = os.getenv("DATABASE_PATH", "database.db")
