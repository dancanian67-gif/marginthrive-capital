#!/usr/bin/env python3
"""Print operational diagnostics summary (Phase E4).

Usage:
    python tools/operational_diagnostics.py
    python tools/operational_diagnostics.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv()

from utils.diagnostics import build_operational_diagnostics, format_diagnostics_report, log_diagnostics_summary


def main() -> int:
    parser = argparse.ArgumentParser(description="MarginThrive operational diagnostics")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    parser.add_argument("--quiet-log", action="store_true", help="Skip structured startup log line")
    args = parser.parse_args()

    if not args.quiet_log:
        report = log_diagnostics_summary(verbose=False)
    else:
        report = build_operational_diagnostics()

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(format_diagnostics_report(report))

    return 0 if report["overall"] in ("ok", "warn") else 1


if __name__ == "__main__":
    sys.exit(main())
