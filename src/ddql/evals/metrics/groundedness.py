"""Groundedness.

    groundedness = Σ(salience × supported) / Σ(salience)

Salience-weighted because a suite that treats "the director's name is spelled
right" and "the company is under sanction" as equal-weight claims will report
a healthy number while the output is dangerous.
"""

from __future__ import annotations

from collections.abc import Sequence

from ddql.types import Claim, ClaimVerdict


def groundedness(
    claims: Sequence[Claim],
    verdicts: Sequence[ClaimVerdict],
) -> float:
    if not claims:
        return 0.0
    by_id = {v.claim_id: v for v in verdicts}
    total = sum(c.salience for c in claims)
    if total == 0:
        return 0.0
    supported = sum(
        c.salience for c in claims if (v := by_id.get(c.id)) and v.supported
    )
    return supported / total


def abstention_rate(
    verdicts: Sequence[ClaimVerdict], *, threshold: float = 0.55
) -> float:
    if not verdicts:
        return 0.0
    return sum(1 for v in verdicts if v.confidence < threshold) / len(verdicts)


def per_dimension_rollup(
    claims: Sequence[Claim],
    verdicts: Sequence[ClaimVerdict],
) -> dict[str, float]:
    """Break groundedness down by claim salience band.

    Engineer:  "groundedness is 0.91"
    Analyst:   "9 of 10 high-salience claims are grounded; the miss is mid-salience"
    Customer:  "the headline findings are solid; one supporting detail needs a look"
    """
    by_id = {v.claim_id: v for v in verdicts}
    bands = {"high": (0.7, 1.01), "mid": (0.3, 0.7), "low": (0.0, 0.3)}
    out: dict[str, float] = {}
    for name, (lo, hi) in bands.items():
        band = [c for c in claims if lo <= c.salience < hi]
        if not band:
            continue
        total = sum(c.salience for c in band)
        supported = sum(
            c.salience for c in band if (v := by_id.get(c.id)) and v.supported
        )
        out[f"groundedness_{name}_salience"] = supported / total if total else 0.0
    return out