"""Source quality.

    source_quality = Σ(salience × tier_weight) / Σ(salience)   (lower is better)

Salience-weighted because a tier-4 source supporting a throwaway aside is
fine; a tier-4 source supporting the headline is not.

Regression here catches the 2026-03-11 incident: primary registry timeouts
caused a silent fallback to aggregators. Groundedness barely moved. Source
quality moved from 2.1 to 2.9 and the taint caught it.
"""

from __future__ import annotations

from collections.abc import Sequence

from ddql.types import Claim, Source

TIER_WEIGHTS: dict[int, float] = {1: 1.0, 2: 1.7, 3: 2.4, 4: 3.0}


def source_quality(claims: Sequence[Claim], sources: Sequence[Source]) -> float:
    by_id = {s.id: s for s in sources}
    total_salience = 0.0
    weighted = 0.0

    for claim in claims:
        cited = [by_id[sid] for sid in claim.citation_ids if sid in by_id]
        if not cited:
            continue
        best = min(TIER_WEIGHTS.get(s.tier, 4.0) for s in cited)
        weighted += claim.salience * best
        total_salience += claim.salience

    return weighted / total_salience if total_salience else 0.0


def coverage(sources: Sequence[Source]) -> dict[str, float]:
    if not sources:
        return {"tier_1_share": 0.0, "tier_4_share": 0.0}
    n = len(sources)
    return {
        "tier_1_share": sum(1 for s in sources if s.tier == 1) / n,
        "tier_4_share": sum(1 for s in sources if s.tier == 4) / n,
    }


THRESHOLDS = {
    "source_quality": 2.30,
    "tier_1_share": 0.35,
    "tier_4_share": 0.15,
}


def failures(weighted_tier: float, dist: dict[str, float]) -> list[str]:
    out: list[str] = []
    if weighted_tier > THRESHOLDS["source_quality"]:
        out.append(
            f"source_quality {weighted_tier:.2f} > {THRESHOLDS['source_quality']}"
        )
    if dist.get("tier_1_share", 0.0) < THRESHOLDS["tier_1_share"]:
        out.append(
            f"tier_1_share {dist['tier_1_share']:.2f} < "
            f"{THRESHOLDS['tier_1_share']}"
        )
    if dist.get("tier_4_share", 0.0) > THRESHOLDS["tier_4_share"]:
        out.append(
            f"tier_4_share {dist['tier_4_share']:.2f} > "
            f"{THRESHOLDS['tier_4_share']}"
        )
    return out