"""Hallucination rate — split into two numbers.

    unsupported_rate   = claims with no supporting source / total claims
    contradicted_rate  = claims a source actively contradicts / total claims

An unsupported claim is a coverage problem. A contradicted claim is a
correctness problem. Collapsing these hides the difference, and the difference
determines whether you ship.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ddql.types import Claim, ClaimVerdict


@dataclass(frozen=True, slots=True)
class HallucinationReport:
    unsupported_rate: float
    contradicted_rate: float
    total_claims: int
    unsupported_claims: int
    contradicted_claims: int

    @property
    def worst_offenders_are_contradictions(self) -> bool:
        return self.contradicted_rate > 0.0


def hallucination(
    claims: Sequence[Claim],
    verdicts: Sequence[ClaimVerdict],
) -> HallucinationReport:
    if not claims:
        return HallucinationReport(0.0, 0.0, 0, 0, 0)

    by_id = {v.claim_id: v for v in verdicts}
    unsupported = 0
    contradicted = 0
    for c in claims:
        v = by_id.get(c.id)
        if v is None:
            unsupported += 1
            continue
        if v.contradicted:
            contradicted += 1
        elif not v.supported:
            unsupported += 1

    n = len(claims)
    return HallucinationReport(
        unsupported_rate=unsupported / n,
        contradicted_rate=contradicted / n,
        total_claims=n,
        unsupported_claims=unsupported,
        contradicted_claims=contradicted,
    )


# Contradictions get a much tighter tolerance than unsupported claims.
# An unsupported claim is a gap; a contradicted claim is a lie.
THRESHOLDS = {
    "unsupported_rate": 0.08,
    "contradicted_rate": 0.005,
}


def failures(report: HallucinationReport) -> list[str]:
    out: list[str] = []
    if report.unsupported_rate > THRESHOLDS["unsupported_rate"]:
        out.append(
            f"unsupported_rate {report.unsupported_rate:.3f} > "
            f"{THRESHOLDS['unsupported_rate']}"
        )
    if report.contradicted_rate > THRESHOLDS["contradicted_rate"]:
        out.append(
            f"contradicted_rate {report.contradicted_rate:.3f} > "
            f"{THRESHOLDS['contradicted_rate']}"
        )
    return out