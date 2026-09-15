"""Golden datasets are content-hashed and versioned like code.

An eval report without a dataset hash is not evidence. If the golden set
changed between Monday and Friday, the two reports are not comparable, and any
tool that presents them side by side is lying.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Manifest:
    version: str
    hash: str
    case_count: int
    changelog: tuple[str, ...]
    owners: tuple[str, ...]


def compute_hash(cases_path: Path) -> str:
    """Stable hash over the sorted case lines. Sorted so reordering the file
    doesn't change the hash — only content does."""
    lines = sorted(
        line.strip()
        for line in cases_path.read_text().splitlines()
        if line.strip()
    )
    digest = hashlib.sha256("\n".join(lines).encode()).hexdigest()
    return f"sha256:{digest[:16]}"


def load_manifest(dataset_dir: Path) -> Manifest:
    manifest_path = dataset_dir / "manifest.json"
    raw = json.loads(manifest_path.read_text())

    cases_path = dataset_dir / "cases.jsonl"
    actual = compute_hash(cases_path)

    if raw["hash"] != actual:
        raise ValueError(
            f"Dataset hash mismatch in {dataset_dir}: "
            f"manifest says {raw['hash']}, cases compute to {actual}. "
            "The golden set was edited without bumping the manifest. "
            "Fix the manifest or revert the edit — do not proceed."
        )

    return Manifest(
        version=raw["version"],
        hash=raw["hash"],
        case_count=raw["case_count"],
        changelog=tuple(raw.get("changelog", ())),
        owners=tuple(raw.get("owners", ())),
    )