#!/usr/bin/env python
"""Fetch the last green T2 baseline from the reports cache.

In CI this pulls from the artifact store. Locally this is a no-op that writes
an empty baseline — a missing baseline is not a failure, it just means the
run has no drift comparison.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=Path("baseline-cache"))
    args = parser.parse_args()

    candidates = sorted(args.cache.glob("*.json")) if args.cache.exists() else []
    if not candidates:
        args.out.write_text("{}")
        print("[fetch_baseline] no cached baseline; writing empty")
        return 0

    latest = candidates[-1]
    args.out.write_text(latest.read_text())
    print(f"[fetch_baseline] using {latest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())