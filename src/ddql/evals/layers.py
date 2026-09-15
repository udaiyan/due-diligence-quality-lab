"""The four evaluation layers.

Each layer is independent: it takes a case and an output, returns a
LayerResult. Layers run cheap → expensive. A layer that fails short-circuits
the rest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ddql.evals.metrics import entity_resolution as er
from ddql.evals.metrics import groundedness as gnd
from ddql.evals.metrics import hallucination as hal
from ddql.evals.metrics import source_quality as sq
from ddql.evals.metrics import timeline as tl
from ddql.segments import by_ref
from ddql.types import (
    ClaimVerdict,
    EvalCase,
    InvestigationOutput,
    RiskVerdict,
    TimelineVerdict,
)


@dataclass(slots=True)
class LayerResult:
    name: str
    metrics: dict[str, float] = field(default_factory=dict)
    taints: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    claim_verdicts: list[ClaimVerdict] = field(default_factory=list)
    risk_verdicts: list[RiskVerdict] = field(default_factory=list)
    timeline_verdicts: list[TimelineVerdict] = field(default_factory=list)


class Layer(Protocol):
    name: str
    def evaluate(self, case: EvalCase, output: InvestigationOutput) -> LayerResult: ...


class L0Deterministic:
    """Schema, citation presence, framework coverage, sanctions source-tier.
    No LLM calls. Runs in milliseconds."""

    name = "L0"

    def evaluate(self, case: EvalCase, output: InvestigationOutput) -> LayerResult:
        result = LayerResult(name=self.name)

        uncited = [c for c in output.claims if not c.citation_ids]
        if uncited:
            result.failures.append(
                f"{len(uncited)} uncited claims: {[c.id for c in uncited][:3]}"
            )

        source_ids = {s.id for s in output.sources}
        dangling = [
            (c.id, sid) for c in output.claims
            for sid in c.citation_ids if sid not in source_ids
        ]
        if dangling:
            result.failures.append(
                f"{len(dangling)} dangling citations: {dangling[:3]}"
            )

        try:
            framework = by_ref(case.risk_framework_id)
        except KeyError:
            result.failures.append(f"unknown risk framework {case.risk_framework_id}")
            framework = None

        if framework is not None:
            scored = {s.category for s in output.risk_scores}
            missing = [c.id for c in framework.categories if c.id not in scored]
            if missing:
                result.failures.append(f"missing risk categories: {missing}")

        for claim in output.claims:
            if claim.risk_category == "sanctions":
                cited = [s for s in output.sources if s.id in claim.citation_ids]
                if cited and all(s.tier > 1 for s in cited):
                    result.failures.append(
                        f"claim {claim.id}: sanctions assertion cites no "
                        f"primary source (tiers: {[s.tier for s in cited]})"
                    )

        result.metrics["l0_claims_total"] = float(len(output.claims))
        result.metrics["l0_uncited_claims"] = float(len(uncited))
        return result


class L1Automated:
    """Entity resolution, source quality, risk bands, timeline. No LLM calls."""

    name = "L1"

    def evaluate(self, case: EvalCase, output: InvestigationOutput) -> LayerResult:
        result = LayerResult(name=self.name)

        er_report = er.entity_resolution(
            output.entities, case.expected_entities, case_tags=case.tags,
        )
        result.metrics.update({
            "entity_resolution.precision": er_report.precision,
            "entity_resolution.recall": er_report.recall,
            "entity_resolution.f1": er_report.f1,
            "entity_resolution.ece": er_report.ece,
        })
        d = er_report.disambiguation
        if d.same_name_accuracy:
            result.metrics["entity_resolution.same_name_accuracy"] = d.same_name_accuracy
        if d.transliteration_f1:
            result.metrics["entity_resolution.transliteration_f1"] = d.transliteration_f1
        if d.corporate_structure_accuracy:
            result.metrics["entity_resolution.corporate_structure_accuracy"] = (
                d.corporate_structure_accuracy
            )
        result.failures.extend(er.failures(er_report))

        wq = sq.source_quality(output.claims, output.sources)
        dist = sq.coverage(output.sources)
        result.metrics["source_quality"] = wq
        result.metrics.update(dist)
        result.failures.extend(sq.failures(wq, dist))

        try:
            framework = by_ref(case.risk_framework_id)
        except KeyError:
            framework = None

        if framework is not None:
            claim_ids = {c.id for c in output.claims}
            for score in output.risk_scores:
                band = case.expected_risk_bands.get(score.category)
                if band is None:
                    continue
                lo, hi = band
                in_band = lo <= score.score <= hi
                justified = any(cid in claim_ids for cid in score.citation_ids)
                result.risk_verdicts.append(RiskVerdict(
                    category=score.category,
                    in_band=in_band,
                    justified=justified,
                    human_band=band,
                    rationale=(
                        f"score {score.score:.0f} vs band ({lo:.0f},{hi:.0f})"
                        if not in_band else "in band"
                    ),
                ))
                if not in_band:
                    result.failures.append(
                        f"risk.{score.category}: score {score.score:.0f} "
                        f"outside band ({lo:.0f},{hi:.0f})"
                    )
                if not justified:
                    result.taints.append(
                        f"risk.{score.category}: score not justified by any cited claim"
                    )

        tl_report = tl.evaluate_timeline(
            output.timeline,
            expected_event_ids=case.expected_timeline_event_ids,
            sources=output.sources,
        )
        result.metrics.update({
            "timeline.ordering_accuracy": tl_report.ordering_accuracy,
            "timeline.completeness": tl_report.completeness,
            "timeline.precision": tl_report.precision,
            "timeline.date_precision_honesty": tl_report.date_precision_honesty,
            "timeline.anachronism_rate": tl_report.anachronism_rate,
            "timeline.undated_rate": tl_report.undated_rate,
        })
        result.failures.extend(tl.failures(tl_report))
        for event in output.timeline:
            result.timeline_verdicts.append(TimelineVerdict(
                event_id=event.id,
                ordering_correct=True,
                date_precision_honest=True,
                anachronistic=False,
                rationale="",
            ))

        return result


class L2LLMJudge:
    name = "L2"

    def __init__(self, judge=None) -> None:
        self._judge = judge

    def evaluate(self, case: EvalCase, output: InvestigationOutput) -> LayerResult:
        result = LayerResult(name=self.name)

        if self._judge is None:
            result.taints.append("L2 skipped: no judge configured")
            return result

        by_id = {s.id: s for s in output.sources}
        verdicts: list[ClaimVerdict] = [
            self._judge.judge_claim(c, by_id) for c in output.claims
        ]
        result.claim_verdicts = list(verdicts)

        g = gnd.groundedness(output.claims, verdicts)
        h = hal.hallucination(output.claims, verdicts)
        result.metrics["groundedness"] = g
        result.metrics["hallucination.unsupported_rate"] = h.unsupported_rate
        result.metrics["hallucination.contradicted_rate"] = h.contradicted_rate
        result.metrics["judge.abstention_rate"] = gnd.abstention_rate(verdicts)
        result.metrics.update(gnd.per_dimension_rollup(output.claims, verdicts))

        result.failures.extend(hal.failures(h))
        if g < 0.85:
            result.failures.append(f"groundedness {g:.3f} < 0.85")

        return result


class L3HumanReview:
    """In production this is a human workflow. In CI, this is a no-op unless
    a human-verdict fixture is configured."""

    name = "L3"

    def evaluate(self, case: EvalCase, output: InvestigationOutput) -> LayerResult:
        return LayerResult(name=self.name)


def build_layer(name: str) -> Layer:
    name = name.strip().upper()
    if name == "L0":
        return L0Deterministic()
    if name == "L1":
        return L1Automated()
    if name == "L2":
        from ddql.evals.judges.llm_judge import build_default_judge
        return L2LLMJudge(judge=build_default_judge())
    if name == "L3":
        return L3HumanReview()
    raise ValueError(f"unknown layer {name}")