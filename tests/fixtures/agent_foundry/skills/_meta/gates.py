#!/usr/bin/env python3
"""Fixture gates script — minimal stand-in for upstream gates.py.

Not executed by tests — just verified to classify as kind='gate-script'.
"""
import sys
from pathlib import Path

SKILLS_ROOT = Path.home() / ".claude" / "skills"


def main() -> int:
    sys.stderr.write(f"fixture gates.py at {SKILLS_ROOT}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
