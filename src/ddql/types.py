"""Core domain types.

The output under test is a structured risk report, not a chatbot reply.
Every field here corresponds to something a customer reads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Literal


class Segment(StrEnum):
    """Customer segment. Drives which risk framework applies and which golden
    cohort a case belongs to. Aggregate metrics across segments hide cohort
    regressions — see ADR-004."""

    LAW_FIRM = "law_firm"
    PRIVATE_BANK = "private_bank"
    UNIVERSITY = "university"
    NONPROFIT = "nonprofit"
    CORPORATE = "corporate"
    PROFESSIONAL_SERVICES = "professional_services"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class Source:
    """A cited source.

    tier drives source_quality. retrieved_at and published_at drive
    anachronism checks: a claim cannot cite a source published after the
    event it describes.
    """

    id: str
    url: str
    tier: int  # 1 = primary/registry, 2 = reputable secondary, 3 = aggregator, 4 = unverified
    retrieved_at: datetime
    published_at: datetime | None = None
    publisher: str = ""


@dataclass(frozen=True, slots=True)
class Claim:
    """A factual assertion in the report.

    salience (0–1) is assigned by the rubric, not guessed. A hallucinated
    headline hurts more than a hallucinated aside, and the metric should
    reflect that — but the weighting is a policy decision, so it lives in
    the rubric.
    """

    id: str
    text: str
    citation_ids: tuple[str, ...]
    salience: float = 1.0
    risk_category: str | None = None


@dataclass(frozen=True, slots=True)
class Entity:
    """A resolved person, org, or location.

    `confidence` feeds entity-resolution calibration. `identifiers` is what
    makes disambiguation auditable: a resolver that says "this is John Smith"
    and cites a Wikidata QID can be checked. One that says "this is John
    Smith" and cites nothing is guessing.
    """

    name: str
    kind: Literal["person", "org", "location"]
    identifiers: dict[str, str] = field(default_factory=dict)
    confidence: float = 1.0
    disambiguation_hint: str | None = None


@dataclass(frozen=True, slots=True)
class RiskScore:
    """One risk score within a framework.

    `confidence` is distinct from `score`. "Score 85, confidence 0.6" means
    "we think this is high risk but we are not certain". That distinction is
    why the calibration metric exists.
    """

    category: str
    score: float  # 0–100
    severity: Severity
    confidence: float  # 0–1
    rationale: str
    citation_ids: tuple[str, ...]
    driven_by_event_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    """One dated event in the report timeline.

    `date_precision` is honest about what the source supports. A source that
    says "2021" supports YEAR, not DAY. Claiming DAY when the source says
    YEAR is a precision lie.
    """

    id: str
    description: str
    date: date | None
    date_precision: Literal["day", "month", "year", "decade", "unknown"]
    event_type: str
    citation_ids: tuple[str, ...]
    salience: float = 1.0


@dataclass(frozen=True, slots=True)
class InvestigationOutput:
    """A full report. This is what the eval harness receives."""

    case_id: str
    tenant: str
    segment: Segment
    risk_framework_id: str
    executive_summary: str
    claims: tuple[Claim, ...]
    entities: tuple[Entity, ...]
    sources: tuple[Source, ...]
    risk_scores: tuple[RiskScore, ...]
    timeline: tuple[TimelineEvent, ...]


@dataclass(frozen=True, slots=True)
class EvalCase:
    """One golden case, in datasets/golden/<version>/cases.jsonl.

    Segment and framework are mandatory. A case without them cannot be
    evaluated against segment-specific thresholds, and the loader will
    reject it.
    """

    id: str
    query: str
    tenant: str
    segment: Segment
    risk_framework_id: str
    rubric_id: str
    expected_entities: tuple[Entity, ...]
    expected_source_tiers: dict[str, int]
    expected_risk_bands: dict[str, tuple[float, float]]
    expected_timeline_event_ids: tuple[str, ...]
    tags: tuple[str, ...] = ()
    notes: str = ""


class Verdict(StrEnum):
    """Three-valued, not boolean. See ADR-003.

    PASS     — every signal in band, dataset hash matches baseline.
    TAINTED  — signals in band, but something upstream degraded. A human
               should look. The green tick that's lying.
    FAIL     — a hard threshold was breached, or a layer raised.
    """

    PASS = "pass"
    TAINTED = "tainted"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class ClaimVerdict:
    claim_id: str
    supported: bool
    contradicted: bool
    confidence: float
    rationale: str = ""
    judge_id: str = ""


@dataclass(frozen=True, slots=True)
class RiskVerdict:
    category: str
    in_band: bool
    justified: bool
    human_band: tuple[float, float] | None
    rationale: str = ""


@dataclass(frozen=True, slots=True)
class TimelineVerdict:
    event_id: str
    ordering_correct: bool
    date_precision_honest: bool
    anachronistic: bool
    rationale: str = ""


@dataclass(frozen=True, slots=True)
class CaseReport:
    case_id: str
    segment: Segment
    verdict: Verdict
    metrics: dict[str, float]
    claim_verdicts: tuple[ClaimVerdict, ...]
    risk_verdicts: tuple[RiskVerdict, ...]
    timeline_verdicts: tuple[TimelineVerdict, ...]
    taints: tuple[str, ...]
    failures: tuple[str, ...]
    dataset_hash: str
    layers_run: tuple[str, ...]
    layers_skipped: tuple[str, ...]
    duration_ms: int