#!/usr/bin/env python
"""Recompute the golden dataset hash and write it into the manifest.

    uv run python scripts/pin_dataset_hash.py datasets/golden/v2
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ddql.evals.datasets.versioning import compute_hash


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset_dir", type=Path)
    args = parser.parse_args()

    manifest_path = args.dataset_dir / "manifest.json"
    cases_path = args.dataset_dir / "cases.jsonl"

    if not manifest_path.exists():
        print(f"manifest not found: {manifest_path}", file=sys.stderr)
        return 1
    if not cases_path.exists():
        print(f"cases file not found: {cases_path}", file=sys.stderr)
        return 1

    new_hash = compute_hash(cases_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    old_hash = manifest.get("hash", "")
    manifest["hash"] = new_hash
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    if old_hash == new_hash:
        print(f"hash already correct: {new_hash}")
    else:
        print(f"updated {manifest_path}: {old_hash} -> {new_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())