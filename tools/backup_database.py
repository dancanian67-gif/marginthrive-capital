#!/usr/bin/env python3
"""Create a timestamped SQLite backup of the MarginThrive operational database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from utils.backup import backup_database
from utils.ops_logging import configure_ops_logging


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup the MarginThrive SQLite database.")
    parser.add_argument(
        "--destination-dir",
        default=None,
        help="Directory for backup files (defaults to BACKUP_DIR env or ./backups).",
    )
    args = parser.parse_args()

    configure_ops_logging()
    try:
        destination = backup_database(destination_dir=args.destination_dir)
    except FileNotFoundError as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        return 1

    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
