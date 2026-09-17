"""Load golden cases from JSONL."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ddql.types import Entity, EvalCase, Segment

if TYPE_CHECKING:
    from ddql.types import InvestigationOutput


def load_cases(path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for lineno, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            cases.append(_to_eval_case(raw))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"{path}:{lineno}: {exc}") from exc
    return cases


def _to_eval_case(raw: dict[str, Any]) -> EvalCase:
    return EvalCase(
        id=raw["id"],
        query=raw["query"],
        tenant=raw["tenant"],
        segment=Segment(raw["segment"]),
        risk_framework_id=raw["risk_framework_id"],
        rubric_id=raw["rubric_id"],
        expected_entities=tuple(_to_entity(e) for e in raw["expected_entities"]),
        expected_source_tiers=dict(raw.get("expected_source_tiers", {})),
        expected_risk_bands={
            k: (float(v[0]), float(v[1]))
            for k, v in raw.get("expected_risk_bands", {}).items()
        },
        expected_timeline_event_ids=tuple(raw.get("expected_timeline_event_ids", ())),
        tags=tuple(raw.get("tags", ())),
        notes=raw.get("notes", ""),
    )


def _to_entity(raw: dict[str, Any]) -> Entity:
    return Entity(
        name=raw["name"],
        kind=raw["kind"],
        identifiers=dict(raw.get("identifiers", {})),
        confidence=float(raw.get("confidence", 1.0)),
        disambiguation_hint=raw.get("disambiguation_hint"),
    )


def to_investigation_output(raw: dict[str, Any]) -> InvestigationOutput:
    from ddql.types import (
        Claim,
        InvestigationOutput,
        RiskScore,
        Severity,
        Source,
        TimelineEvent,
    )

    def _dt(s: str | None) -> datetime | None:
        return datetime.fromisoformat(s) if s else None

    def _d(s: str | None) -> date | None:
        return date.fromisoformat(s) if s else None

    return InvestigationOutput(
        case_id=raw["case_id"],
        tenant=raw["tenant"],
        segment=Segment(raw["segment"]),
        risk_framework_id=raw["risk_framework_id"],
        executive_summary=raw.get("executive_summary", ""),
        claims=tuple(
            Claim(
                id=c["id"], text=c["text"],
                citation_ids=tuple(c.get("citation_ids", ())),
                salience=float(c.get("salience", 1.0)),
                risk_category=c.get("risk_category"),
            )
            for c in raw.get("claims", ())
        ),
        entities=tuple(_to_entity(e) for e in raw.get("entities", ())),
        sources=tuple(
            Source(
                id=s["id"], url=s["url"], tier=int(s["tier"]),
                retrieved_at=_dt(s["retrieved_at"]) or datetime.now(),
                published_at=_dt(s.get("published_at")),
                publisher=s.get("publisher", ""),
            )
            for s in raw.get("sources", ())
        ),
        risk_scores=tuple(
            RiskScore(
                category=r["category"], score=float(r["score"]),
                severity=Severity(r["severity"]), confidence=float(r["confidence"]),
                rationale=r.get("rationale", ""),
                citation_ids=tuple(r.get("citation_ids", ())),
                driven_by_event_ids=tuple(r.get("driven_by_event_ids", ())),
            )
            for r in raw.get("risk_scores", ())
        ),
        timeline=tuple(
            TimelineEvent(
                id=t["id"], description=t["description"],
                date=_d(t.get("date")),
                date_precision=t.get("date_precision", "unknown"),
                event_type=t.get("event_type", "unknown"),
                citation_ids=tuple(t.get("citation_ids", ())),
                salience=float(t.get("salience", 1.0)),
            )
            for t in raw.get("timeline", ())
        ),
    )