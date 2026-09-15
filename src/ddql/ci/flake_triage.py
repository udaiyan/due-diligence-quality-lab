"""Flake triage.

Most teams retry. Retries hide bugs. This classifies.

Input:  a failure (test id, trace, run history)
Output: a FlakeClass + evidence + suggested action

Deterministic heuristics first; Claude Code as a tiebreaker for UNKNOWN.
Every Claude suggestion a human overrides is logged and becomes a labelled
example.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol


class FlakeClass(StrEnum):
    SELECTOR_DRIFT = "selector_drift"
    TIMING = "timing"
    DATA_STATE = "data_state"
    INFRA = "infra"
    GENUINE_BUG = "genuine_bug"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Triage:
    test_id: str
    flake_class: FlakeClass
    confidence: float
    evidence: tuple[str, ...]
    suggested_action: str
    classifier_agreed: bool = True


class TriageBackend(Protocol):
    def classify(
        self, *, test_id: str, trace_summary: str
    ) -> dict[str, Any]: ...


def _looks_like_selector_drift(
    history: list[dict[str, Any]], trace: str
) -> bool:
    if "TimeoutError" not in trace and "not found" not in trace.lower():
        return False
    recent = history[-10:]
    if not recent:
        return False
    pass_then_fail = recent[-1]["status"] == "fail" and any(
        h["status"] == "pass" for h in recent[:-1]
    )
    return pass_then_fail and "locator" in trace.lower()


def _looks_like_timing(
    history: list[dict[str, Any]], trace: str
) -> bool:
    statuses = [h["status"] for h in history[-20:]]
    if not statuses:
        return False
    flaky = 0 < statuses.count("fail") < len(statuses)
    return flaky and ("waiting for" in trace.lower() or "race" in trace.lower())


def _looks_like_data_state(
    history: list[dict[str, Any]], trace: str
) -> bool:
    if not history:
        return False
    passes_alone = any(
        h.get("run_scope") == "solo" and h["status"] == "pass" for h in history
    )
    fails_together = any(
        h.get("run_scope") == "suite" and h["status"] == "fail" for h in history
    )
    return passes_alone and fails_together


def _looks_like_infra(
    history: list[dict[str, Any]], trace: str
) -> bool:
    markers = ("502", "503", "504", "ECONNRESET", "ENOTFOUND", "dial tcp")
    return any(m in trace for m in markers)


def _looks_like_genuine_bug(trace: str) -> bool:
    return "AssertionError" in trace and "expected" in trace.lower()


_ACTIONS = {
    FlakeClass.SELECTOR_DRIFT: (
        "Autofile selector-sync PR via Claude Code. Reviewer answers one "
        "question: is this still the semantically correct element?"
    ),
    FlakeClass.TIMING: (
        "Replace implicit wait with an explicit wait-for-condition. "
        "Never a sleep. Cite the trace span in the commit message."
    ),
    FlakeClass.DATA_STATE: (
        "Scope the tenant fixture to the test. File a bug against the fixture "
        "if it leaked — this will recur."
    ),
    FlakeClass.INFRA: (
        "Flag as infra, do not retry silently. If infra flake rate > 2% over "
        "a week, escalate to platform."
    ),
    FlakeClass.GENUINE_BUG: (
        "Page the owning squad. The test was right and the app was wrong."
    ),
    FlakeClass.UNKNOWN: (
        "Escalate with the trace attached. Do NOT retry — an unclassified "
        "flake is a bug we haven't understood yet."
    ),
}


def triage(
    *,
    test_id: str,
    trace: str,
    history: list[dict[str, Any]],
    backend: TriageBackend | None = None,
) -> Triage:
    trace_summary = _summarise(trace)

    for flake_class, predicate in (
        (FlakeClass.INFRA, _looks_like_infra),
        (FlakeClass.SELECTOR_DRIFT, _looks_like_selector_drift),
        (FlakeClass.DATA_STATE, _looks_like_data_state),
        (FlakeClass.TIMING, _looks_like_timing),
        (FlakeClass.GENUINE_BUG, lambda h, t: _looks_like_genuine_bug(t)),
    ):
        if predicate(history, trace):
            return Triage(
                test_id=test_id,
                flake_class=flake_class,
                confidence=0.85,
                evidence=(_first_matching_line(trace, flake_class),),
                suggested_action=_ACTIONS[flake_class],
            )

    if backend is not None:
        suggestion = backend.classify(test_id=test_id, trace_summary=trace_summary)
        flake_class = FlakeClass(suggestion["flake_class"])
        return Triage(
            test_id=test_id,
            flake_class=flake_class,
            confidence=float(suggestion.get("confidence", 0.5)),
            evidence=tuple(suggestion.get("evidence", ())),
            suggested_action=_ACTIONS[flake_class],
            classifier_agreed=False,
        )

    return Triage(
        test_id=test_id,
        flake_class=FlakeClass.UNKNOWN,
        confidence=0.0,
        evidence=(trace_summary,),
        suggested_action=_ACTIONS[FlakeClass.UNKNOWN],
    )


def _summarise(trace: str, *, max_lines: int = 40) -> str:
    keywords = ("Error", "error", "Timeout", "expect", "locator", "waiting", "5")
    lines = [ln for ln in trace.splitlines() if any(k in ln for k in keywords)]
    return "\n".join(lines[:max_lines])


def _first_matching_line(trace: str, flake_class: FlakeClass) -> str:
    needles = {
        FlakeClass.INFRA: ("502", "503", "504", "ECONNRESET", "ENOTFOUND"),
        FlakeClass.SELECTOR_DRIFT: ("TimeoutError", "not found", "locator"),
        FlakeClass.DATA_STATE: ("fixture", "tenant", "leaked"),
        FlakeClass.TIMING: ("waiting for", "race"),
        FlakeClass.GENUINE_BUG: ("AssertionError", "expected"),
        FlakeClass.UNKNOWN: (),
    }[flake_class]
    for line in trace.splitlines():
        if any(n in line for n in needles):
            return line.strip()
    return ""


def to_issue_body(triage_result: Triage, trace_path: Path) -> str:
    evidence = "\n".join(f"- `{e}`" for e in triage_result.evidence)
    return f"""\
### Flake triage: `{triage_result.test_id}`

**Class:** `{triage_result.flake_class}` (confidence {triage_result.confidence:.2f})

**Evidence**
{evidence}

**Suggested action**
{triage_result.suggested_action}

**Trace:** `{trace_path}`

---
<sub>Classified by `ddql.ci.flake_triage`. If this is wrong, override the
label on this issue — overrides become labelled training examples.</sub>
"""


def _main() -> int:
    parser = argparse.ArgumentParser(description="Classify a flaky test.")
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--traces", type=Path)
    parser.add_argument("--autofile-issues", action="store_true")
    args = parser.parse_args()

    if not args.junit.exists():
        print(f"junit report not found: {args.junit}", file=sys.stderr)
        return 1

    print(f"[flake_triage] reading {args.junit}")
    print("[flake_triage] classifier integration is wired in production; "
          "this is the reference entry point.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())