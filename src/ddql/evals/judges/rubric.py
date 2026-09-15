"""Rubrics as versioned data, not prompt strings.

A rubric is the contract between the judge, the golden set, and the humans
who calibrate it. If the rubric changes, the judge changes, and the change is
visible in the changelog. Prompt drift is a real failure mode (see RESULTS.md,
2026-03-14) and this is the structural defence against it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, slots=True)
class Dimension:
    id: str
    question: str
    weight: float
    fail_if: str


@dataclass(frozen=True, slots=True)
class Rubric:
    id: str
    version: str
    applies_to: str
    dimensions: tuple[Dimension, ...]
    changelog: tuple[str, ...] = field(default_factory=tuple)
    created: date = field(default_factory=date.today)

    def __post_init__(self) -> None:
        total = sum(d.weight for d in self.dimensions)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Rubric {self.id}@{self.version} weights sum to {total}, not 1.0"
            )

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"


GROUNDEDNESS_V3_1 = Rubric(
    id="groundedness",
    version="v3.1",
    applies_to="groundedness",
    dimensions=(
        Dimension(
            id="attribution",
            question="Does the cited source actually contain the claim?",
            weight=0.45,
            fail_if="The source does not mention the entity, fact, or relationship.",
        ),
        Dimension(
            id="entailment",
            question="Does the source, read fairly, support the claim as worded?",
            weight=0.35,
            fail_if=(
                "The source is consistent with the claim but does not entail it — "
                "e.g. the claim overstates scope, certainty, or timeframe."
            ),
        ),
        Dimension(
            id="currency",
            question="Is the source current enough for the claim?",
            weight=0.20,
            fail_if=(
                "The source predates a known change (directorship, address, "
                "sanction status) that the claim asserts as current."
            ),
        ),
    ),
    changelog=(
        "v3.1: currency weight 0.15 → 0.20 after 2026-03-14 contradicted-claim spike",
        "v3.1: reworded entailment fail_if to match L3 human guidance",
        "v3.0: split attribution from entailment; v2 conflated them",
    ),
)