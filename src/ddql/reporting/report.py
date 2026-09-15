"""Report rendering.

to_json   — machine-readable, includes every CaseReport.
to_markdown — human-readable, includes global and per-segment rollups.

Both pin the dataset hash. A report without it is not evidence.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict

from ddql.evals.datasets.versioning import Manifest
from ddql.evals.harness import summarise, summarise_by_segment
from ddql.evals.metrics.risk_calibration import explain as explain_risk
from ddql.evals.metrics.timeline import explain as explain_timeline
from ddql.types import CaseReport


def to_json(
    reports: Sequence[CaseReport],
    summary: dict,
    manifest: Manifest,
) -> str:
    payload = {
        "manifest": asdict(manifest),
        "summary": summary,
        "by_segment": summarise_by_segment(reports),
        "cases": [
            {
                "case_id": r.case_id,
                "segment": str(r.segment),
                "verdict": str(r.verdict),
                "metrics": r.metrics,
                "taints": list(r.taints),
                "failures": list(r.failures),
                "dataset_hash": r.dataset_hash,
                "layers_run": list(r.layers_run),
                "layers_skipped": list(r.layers_skipped),
                "duration_ms": r.duration_ms,
            }
            for r in reports
        ],
    }
    return json.dumps(payload, indent=2, default=str)


def to_markdown(
    reports: Sequence[CaseReport],
    summary: dict,
    manifest: Manifest,
) -> str:
    if not reports:
        return "## Eval report\n\n_No cases ran._\n"

    lines: list[str] = []
    lines.append("## Eval report")
    lines.append("")
    lines.append(f"**Dataset:** `{manifest.version}` · `{manifest.hash}`  ")
    lines.append(f"**Cases:** {summary['cases']}  ")
    lines.append(
        f"**Pass:** {summary['pass']} · "
        f"**Tainted:** {summary['tainted']} · "
        f"**Fail:** {summary['fail']}"
    )
    lines.append("")

    # Global summary
    lines.append("### Global")
    lines.append("")
    lines.append("| Signal | Value |")
    lines.append("|---|---|")
    for k, v in sorted(summary.items()):
        if not k.startswith("mean_"):
            continue
        lines.append(f"| `{k[5:]}` | {v:.4f} |")
    lines.append("")

    # Per-segment
    lines.append("### Per segment")
    lines.append("")
    lines.append("| Segment | Cases | Pass | Tainted | Fail |")
    lines.append("|---|---|---|---|---|")
    for seg, s in sorted(summarise_by_segment(reports).items()):
        lines.append(
            f"| `{seg}` | {s['cases']} | {s['pass']} | {s['tainted']} | {s['fail']} |"
        )
    lines.append("")

    # Failures
    failing = [r for r in reports if r.failures]
    if failing:
        lines.append("### Failures")
        lines.append("")
        for r in failing[:20]:
            lines.append(f"**`{r.case_id}`** (`{r.segment}`)")
            for f in r.failures:
                lines.append(f"- {f}")
            lines.append("")
        if len(failing) > 20:
            lines.append(f"_…and {len(failing) - 20} more. See the JSON report._")
            lines.append("")

    # Taints
    tainted = [r for r in reports if r.taints and not r.failures]
    if tainted:
        lines.append("### Taints (a green tick that might be lying)")
        lines.append("")
        for r in tainted[:10]:
            lines.append(f"**`{r.case_id}`** (`{r.segment}`)")
            for t in r.taints:
                lines.append(f"- {t}")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "_Reports from different dataset hashes are not comparable. "
        "If the hash above does not match your baseline, the comparison is "
        "invalid and this report says so._"
    )
    return "\n".join(lines)


# Re-export explains for callers that want them
__all__ = ["to_json", "to_markdown", "explain_risk", "explain_timeline"]