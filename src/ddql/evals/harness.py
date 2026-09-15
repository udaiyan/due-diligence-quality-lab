"""The layered evaluation harness.

Design principles
-----------------
1. Layers run cheap → expensive. A case that fails L0 never reaches L2.
2. Layers are independent. Each returns a partial LayerResult; the harness
   merges. No layer knows about another's internals.
3. TAINTED exists so a degraded-but-in-band run is visible. See ADR-003.
4. Every report pins the dataset hash it ran against.
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Sequence

from ddql.evals.layers import Layer
from ddql.types import CaseReport, EvalCase, InvestigationOutput, Verdict


class Harness:
    def __init__(
        self,
        layers: Sequence[Layer],
        *,
        baseline: dict[str, float] | None = None,
        drift_tolerance: float = 0.03,
    ) -> None:
        if not layers:
            raise ValueError("Harness needs at least one layer")
        self._layers = tuple(layers)
        self._baseline = baseline or {}
        self._drift_tolerance = drift_tolerance

    def run_case(
        self,
        case: EvalCase,
        output: InvestigationOutput,
        *,
        dataset_hash: str,
    ) -> CaseReport:
        started = time.perf_counter()
        taints: list[str] = []
        failures: list[str] = []
        metrics: dict[str, float] = {}
        claim_verdicts = []
        risk_verdicts = []
        timeline_verdicts = []
        layers_run: list[str] = []
        layers_skipped: list[str] = []

        for layer in self._layers:
            if failures:
                layers_skipped.append(layer.name)
                continue

            result = layer.evaluate(case, output)
            layers_run.append(layer.name)
            metrics.update(result.metrics)
            taints.extend(result.taints)
            failures.extend(result.failures)
            claim_verdicts.extend(result.claim_verdicts)
            risk_verdicts.extend(result.risk_verdicts)
            timeline_verdicts.extend(result.timeline_verdicts)

        taints.extend(self._drift_taints(metrics))

        return CaseReport(
            case_id=case.id,
            segment=case.segment,
            verdict=self._verdict(failures, taints),
            metrics=metrics,
            claim_verdicts=tuple(claim_verdicts),
            risk_verdicts=tuple(risk_verdicts),
            timeline_verdicts=tuple(timeline_verdicts),
            taints=tuple(taints),
            failures=tuple(failures),
            dataset_hash=dataset_hash,
            layers_run=tuple(layers_run),
            layers_skipped=tuple(layers_skipped),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    def run(
        self,
        cases: Iterable[EvalCase],
        outputs: dict[str, InvestigationOutput],
        *,
        dataset_hash: str,
    ) -> list[CaseReport]:
        reports: list[CaseReport] = []
        for case in cases:
            output = outputs.get(case.id)
            if output is None:
                reports.append(
                    CaseReport(
                        case_id=case.id,
                        segment=case.segment,
                        verdict=Verdict.FAIL,
                        metrics={},
                        claim_verdicts=(),
                        risk_verdicts=(),
                        timeline_verdicts=(),
                        taints=(),
                        failures=(f"no output produced for case {case.id}",),
                        dataset_hash=dataset_hash,
                        layers_run=(),
                        layers_skipped=tuple(l.name for l in self._layers),
                        duration_ms=0,
                    )
                )
                continue
            reports.append(self.run_case(case, output, dataset_hash=dataset_hash))
        return reports

    def _drift_taints(self, metrics: dict[str, float]) -> list[str]:
        taints: list[str] = []
        for name, current in metrics.items():
            baseline = self._baseline.get(name)
            if baseline is None or baseline == 0:
                continue
            drop = (baseline - current) / baseline
            if drop > self._drift_tolerance:
                taints.append(
                    f"drift: {name} {current:.4f} vs baseline {baseline:.4f} "
                    f"({drop:+.1%}, tolerance {self._drift_tolerance:.0%})"
                )
        return taints

    @staticmethod
    def _verdict(failures: list[str], taints: list[str]) -> Verdict:
        if failures:
            return Verdict.FAIL
        if taints:
            return Verdict.TAINTED
        return Verdict.PASS


def summarise(reports: Sequence[CaseReport]) -> dict[str, float | int | tuple[str, ...]]:
    """Aggregate a run. This is what T2 compares against the baseline.

    Reports from different dataset hashes are pooled but flagged — the summary
    carries the set of hashes it saw so nobody compares apples to oranges.
    """
    if not reports:
        return {"cases": 0, "dataset_hashes": ()}

    n = len(reports)
    counts = {v: sum(1 for r in reports if r.verdict == v) for v in Verdict}

    metric_names = {k for r in reports for k in r.metrics}
    means = {
        f"mean_{name}": sum(r.metrics.get(name, 0.0) for r in reports) / n
        for name in metric_names
    }

    return {
        "cases": n,
        "pass": counts[Verdict.PASS],
        "tainted": counts[Verdict.TAINTED],
        "fail": counts[Verdict.FAIL],
        "taint_rate": counts[Verdict.TAINTED] / n,
        "fail_rate": counts[Verdict.FAIL] / n,
        **means,
        "dataset_hashes": tuple(sorted({r.dataset_hash for r in reports})),
    }


def summarise_by_segment(
    reports: Sequence[CaseReport],
) -> dict[str, dict[str, float | int | tuple[str, ...]]]:
    """Per-segment rollup. Both the global summary and each segment summary
    must pass their gates — see ADR-004."""
    by_seg: dict[str, list[CaseReport]] = {}
    for r in reports:
        by_seg.setdefault(str(r.segment), []).append(r)
    return {seg: summarise(rs) for seg, rs in by_seg.items()}