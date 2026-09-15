"""Entity resolution — disambiguation is the headline.

Treating "did you find the entity?" as binary misses the failure mode that
matters: finding *an* entity with the right name, but the *wrong* entity.

So we report two things:
  1. Standard P/R/F1 + ECE.
  2. Disambiguation accuracy over same-name and transliteration sub-populations.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from ddql.types import Entity


@dataclass(frozen=True, slots=True)
class DisambiguationReport:
    n_cases: int
    same_name_accuracy: float
    transliteration_f1: float
    corporate_structure_accuracy: float


@dataclass(frozen=True, slots=True)
class ResolutionReport:
    precision: float
    recall: float
    f1: float
    ece: float
    true_positives: int
    false_positives: int
    false_negatives: int
    disambiguation: DisambiguationReport = field(
        default_factory=lambda: DisambiguationReport(0, 0.0, 0.0, 0.0)
    )


def _key(e: Entity) -> str:
    for id_type in ("lei", "companies_house", "wikidata", "sanctions_id"):
        if id_type in e.identifiers:
            return f"{e.kind}:{id_type}:{e.identifiers[id_type]}"
    return f"{e.kind}:name:{e.name.strip().lower()}"


def entity_resolution(
    predicted: Sequence[Entity],
    expected: Sequence[Entity],
    *,
    case_tags: Sequence[str] = (),
    n_bins: int = 10,
) -> ResolutionReport:
    pred_keys = {_key(e) for e in predicted}
    exp_keys = {_key(e) for e in expected}

    tp = len(pred_keys & exp_keys)
    fp = len(pred_keys - exp_keys)
    fn = len(exp_keys - pred_keys)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)

    disambig = DisambiguationReport(
        n_cases=1,
        same_name_accuracy=(
            _same_name_accuracy(predicted, expected)
            if "same_name" in case_tags else 0.0
        ),
        transliteration_f1=(f1 if "transliteration" in case_tags else 0.0),
        corporate_structure_accuracy=(
            _corporate_structure_accuracy(predicted, expected)
            if "ubo_chain" in case_tags else 0.0
        ),
    )

    return ResolutionReport(
        precision=precision,
        recall=recall,
        f1=f1,
        ece=_expected_calibration_error(predicted, exp_keys, n_bins=n_bins),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        disambiguation=disambig,
    )


def _same_name_accuracy(
    predicted: Sequence[Entity], expected: Sequence[Entity]
) -> float:
    if not expected:
        return 0.0
    by_name: dict[str, list[Entity]] = {}
    for e in expected:
        by_name.setdefault(e.name.strip().lower(), []).append(e)

    correct = 0
    for p in predicted:
        candidates = by_name.get(p.name.strip().lower(), [])
        if not candidates:
            continue
        if any(_key(p) == _key(c) for c in candidates):
            correct += 1
    return correct / len(predicted) if predicted else 0.0


def _corporate_structure_accuracy(
    predicted: Sequence[Entity], expected: Sequence[Entity]
) -> float:
    exp_keys = {_key(e) for e in expected}
    pred_keys = {_key(e) for e in predicted}
    if not exp_keys:
        return 0.0
    return len(exp_keys & pred_keys) / len(exp_keys)


def _expected_calibration_error(
    predicted: Sequence[Entity], exp_keys: set[str], *, n_bins: int
) -> float:
    if not predicted:
        return 0.0
    bins: list[list[tuple[float, bool]]] = [[] for _ in range(n_bins)]
    for e in predicted:
        idx = min(int(e.confidence * n_bins), n_bins - 1)
        bins[idx].append((e.confidence, _key(e) in exp_keys))

    n = len(predicted)
    ece = 0.0
    for b in bins:
        if not b:
            continue
        mean_conf = sum(c for c, _ in b) / len(b)
        accuracy = sum(1 for _, ok in b if ok) / len(b)
        ece += (len(b) / n) * abs(mean_conf - accuracy)
    return ece


THRESHOLDS = {
    "f1": 0.90,
    "precision": 0.92,
    "recall": 0.88,
    "ece": 0.08,
    "same_name_accuracy": 0.85,
    "transliteration_f1": 0.82,
    "corporate_structure_accuracy": 0.88,
}


def failures(report: ResolutionReport) -> list[str]:
    out: list[str] = []
    for metric in ("f1", "precision", "recall"):
        value = getattr(report, metric)
        if value < THRESHOLDS[metric]:
            out.append(f"entity_resolution.{metric} {value:.3f} < {THRESHOLDS[metric]}")
    if report.ece > THRESHOLDS["ece"]:
        out.append(f"entity_resolution.ece {report.ece:.3f} > {THRESHOLDS['ece']}")

    d = report.disambiguation
    if d.same_name_accuracy and d.same_name_accuracy < THRESHOLDS["same_name_accuracy"]:
        out.append(
            f"entity_resolution.same_name_accuracy {d.same_name_accuracy:.3f} "
            f"< {THRESHOLDS['same_name_accuracy']}"
        )
    if d.transliteration_f1 and d.transliteration_f1 < THRESHOLDS["transliteration_f1"]:
        out.append(
            f"entity_resolution.transliteration_f1 {d.transliteration_f1:.3f} "
            f"< {THRESHOLDS['transliteration_f1']}"
        )
    if (
        d.corporate_structure_accuracy
        and d.corporate_structure_accuracy < THRESHOLDS["corporate_structure_accuracy"]
    ):
        out.append(
            f"entity_resolution.corporate_structure_accuracy "
            f"{d.corporate_structure_accuracy:.3f} "
            f"< {THRESHOLDS['corporate_structure_accuracy']}"
        )
    return out