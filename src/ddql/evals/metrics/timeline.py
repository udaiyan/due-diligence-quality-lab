"""Timeline quality.

A correctly-grounded set of events presented out of order, or claiming more
date precision than its sources support, is still wrong. The report format
includes a timeline; the timeline is an output, not a view.

Six measures: ordering_accuracy, completeness, precision,
date_precision_honesty, anachronism_rate, undated_rate.

The last one is a gate, not just a signal. A timeline where 40% of events are
undated is less useful than one with fewer, well-dated events. The 2026-03-21
incident was undated events sorted by ingestion time.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from ddql.types import Source, TimelineEvent

_PRECISION_ORDER = {"unknown": 0, "decade": 1, "year": 2, "month": 3, "day": 4}


@dataclass(frozen=True, slots=True)
class TimelineReport:
    ordering_accuracy: float
    completeness: float
    precision: float
    date_precision_honesty: float
    anachronism_rate: float
    undated_rate: float
    expected_count: int
    found_count: int
    matched_count: int


def evaluate_timeline(
    events: Sequence[TimelineEvent],
    *,
    expected_event_ids: Sequence[str],
    sources: Sequence[Source],
) -> TimelineReport:
    expected = set(expected_event_ids)
    found = {e.id for e in events}

    tp = len(expected & found)
    precision = tp / len(found) if found else 0.0
    completeness = tp / len(expected) if expected else 0.0

    dated = [e for e in events if e.date is not None]
    ordering = _ordering_accuracy(dated)
    honesty = _date_precision_honesty(events, sources)
    anachronistic = _anachronism_rate(events, sources)
    undated = sum(1 for e in events if e.date is None) / len(events) if events else 0.0

    return TimelineReport(
        ordering_accuracy=ordering,
        completeness=completeness,
        precision=precision,
        date_precision_honesty=honesty,
        anachronism_rate=anachronistic,
        undated_rate=undated,
        expected_count=len(expected),
        found_count=len(found),
        matched_count=tp,
    )


def _ordering_accuracy(dated: Sequence[TimelineEvent]) -> float:
    if len(dated) < 2:
        return 1.0
    ordered = sorted(dated, key=lambda e: e.date)  # type: ignore[arg-type,return-value]
    inversions = 0
    for a, b in zip(dated, ordered, strict=False):
        if a.id != b.id:
            inversions += 1
    return 1.0 - (inversions / len(dated))


def _date_precision_honesty(
    events: Sequence[TimelineEvent], sources: Sequence[Source]
) -> float:
    if not events:
        return 1.0
    by_id = {s.id: s for s in sources}
    honest = 0
    for e in events:
        cited = [by_id[sid] for sid in e.citation_ids if sid in by_id]
        if not cited:
            continue
        best_supported = max(
            (_precision_of(s.published_at) for s in cited if s.published_at),
            default=_PRECISION_ORDER["year"],
        )
        if _PRECISION_ORDER[e.date_precision] <= best_supported:
            honest += 1
    return honest / len(events)


def _anachronism_rate(
    events: Sequence[TimelineEvent], sources: Sequence[Source]
) -> float:
    """Fraction of dated events whose date is AFTER their earliest cited
    source's publication.

    A source published in 2015 cannot support an event dated 2020 — it
    cannot know about the future. The inverse (event before source) is
    not anachronistic: a 2022 news article legitimately documents a 1971
    birth, and a 2021 Companies House filing legitimately records a 2015
    directorship.

    The earlier version of this check had the comparison inverted, which
    flagged retrospective sourcing as anachronism. See ADR-005.
    """
    dated = [e for e in events if e.date is not None]
    if not dated:
        return 0.0
    by_id = {s.id: s for s in sources}
    anachronistic = 0
    for e in dated:
        pubs: list[datetime] = []
        for sid in e.citation_ids:
            src = by_id.get(sid)
            if src is not None and src.published_at is not None:
                pubs.append(src.published_at)
        if not pubs:
            continue
        earliest = min(pubs)
        if e.date > earliest.date():
            anachronistic += 1
    return anachronistic / len(dated)


def _precision_of(dt: datetime | None) -> int:
    """Approximate precision of a datetime. In production, the extractor
    supplies this; here it's a fallback."""
    if dt is None:
        return _PRECISION_ORDER["year"]
    return _PRECISION_ORDER["day"]


THRESHOLDS = {
    "ordering_accuracy": 0.92,
    "completeness": 0.80,
    "precision": 0.85,
    "date_precision_honesty": 0.90,
    "anachronism_rate": 0.02,
    "undated_rate": 0.20,
}


def failures(report: TimelineReport) -> list[str]:
    out: list[str] = []
    for metric, floor in THRESHOLDS.items():
        value = getattr(report, metric)
        if metric in ("anachronism_rate", "undated_rate"):
            if value > floor:
                out.append(f"timeline.{metric} {value:.3f} > {floor}")
        elif value < floor:
            out.append(f"timeline.{metric} {value:.3f} < {floor}")
    return out


def explain(report: TimelineReport) -> str:
    parts: list[str] = []
    if report.ordering_accuracy < THRESHOLDS["ordering_accuracy"]:
        parts.append("events appear out of chronological order")
    if report.undated_rate > THRESHOLDS["undated_rate"]:
        parts.append(
            f"{report.undated_rate:.0%} of events lack a date, so the "
            f"chronology is incomplete"
        )
    if report.anachronism_rate > THRESHOLDS["anachronism_rate"]:
        parts.append(
            "at least one event is dated before the source that supports it"
        )
    if not parts:
        return "timeline reads in order and is fully dated."
    return "Timeline: " + "; ".join(parts) + "."