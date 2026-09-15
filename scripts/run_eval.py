#!/usr/bin/env python
"""Run the eval harness over a golden dataset and write a report.

    uv run python scripts/run_eval.py \
        --dataset datasets/golden/v2 \
        --layers L0,L1,L2 \
        --baseline baseline.json \
        --report reports/t2.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ddql.evals.datasets.loader import load_cases, to_investigation_output
from ddql.evals.datasets.versioning import load_manifest
from ddql.evals.harness import Harness, summarise
from ddql.evals.layers import build_layer
from ddql.reporting.report import to_json, to_markdown


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--layers", default="L0,L1,L2")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--drift-tolerance", type=float, default=0.03)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--outputs", type=Path,
                        help="JSON file with pre-computed outputs keyed by case id")
    args = parser.parse_args()

    manifest = load_manifest(args.dataset)
    cases = load_cases(args.dataset / "cases.jsonl")

    if args.outputs:
        raw_outputs = json.loads(args.outputs.read_text())
        outputs = {k: to_investigation_output(v) for k, v in raw_outputs.items()}
    else:
        print(
            "no --outputs file provided; wire produce_outputs() to the system "
            "under test before running this for real",
            file=sys.stderr,
        )
        return 2

    baseline = (
        json.loads(args.baseline.read_text())
        if args.baseline and args.baseline.exists()
        else {}
    )
    if baseline and baseline.get("dataset_hashes") not in ([manifest.hash], [manifest.hash,]):
        print(
            f"refusing to compare: baseline ran against "
            f"{baseline.get('dataset_hashes')}, this run is {manifest.hash}",
            file=sys.stderr,
        )
        baseline = {}

    harness = Harness(
        layers=[build_layer(name.strip()) for name in args.layers.split(",")],
        baseline={k[5:]: v for k, v in baseline.items() if k.startswith("mean_")},
        drift_tolerance=args.drift_tolerance,
    )
    reports = harness.run(cases, outputs, dataset_hash=manifest.hash)
    summary = summarise(reports)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(to_json(reports, summary, manifest))
    args.report.with_suffix(".md").write_text(to_markdown(reports, summary, manifest))

    print(
        f"{summary['cases']} cases | "
        f"pass {summary['pass']} | "
        f"tainted {summary['tainted']} | "
        f"fail {summary['fail']} | "
        f"dataset {manifest.hash}"
    )
    return 1 if summary["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())