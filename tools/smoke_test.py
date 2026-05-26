#!/usr/bin/env python3
"""Run operational smoke tests (Phase E4).

Usage:
    python tools/smoke_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operational_tests.smoke_tests import run_smoke_tests


def main() -> int:
    success = run_smoke_tests()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
