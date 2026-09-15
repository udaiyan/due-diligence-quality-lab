"""Risk-score calibration against human analysts.

Two questions, both necessary:

1. Agreement — does the AI's score fall within the band a human analyst would
   give? A score of 85 when the analyst says 20 is wrong regardless of how
   well-grounded the rationale is.
2. Calibration — when the AI says "confidence 0.8", is it right 80% of the
   time?

Plus bias: does the AI systematically over- or under-score certain categories?

Per-category, because aggregate risk calibration hides the category that's
broken. The 2026-03-18 incident was visible only at the integrity category,
which is why the metric breaks it out.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from ddql.segments import RiskFramework
from ddql.types import RiskScore


@dataclass(frozen=True, slots=True)
class CategoryCalibration:
    category: str
    n: int
    agreement_rate: float
    mean_absolute_error: float
    bias: float
    ece: float
    abstention_rate: float


@dataclass(frozen=True, slots=True)
class RiskCalibrationReport:
    overall_agreement: float
    overall_mae: float
    overall_ece: float
    per_category: dict[str, CategoryCalibration] = field(default_factory=dict)

    def worst_category(self) -> str | None:
        if not self.per_category:
            return None
        return max(
            self.per_category,
            key=lambda k: self.per_category[k].mean_absolute_error,
        )


def calibrate(
    predicted: Sequence[RiskScore],
    *,
    human_bands: dict[str, tuple[float, float]],
    framework: RiskFramework,
    n_bins: int = 5,
    abstain_below: float = 0.55,
) -> RiskCalibrationReport:
    by_cat: dict[str, list[RiskScore]] = {c.id: [] for c in framework.categories}
    for s in predicted:
        if s.category in by_cat:
            by_cat[s.category].append(s)

    per_category: dict[str, CategoryCalibration] = {}
    for cat_id, scores in by_cat.items():
        band = human_bands.get(cat_id)
        if band is None or not scores:
            per_category[cat_id] = CategoryCalibration(
                category=cat_id, n=len(scores), agreement_rate=0.0,
                mean_absolute_error=100.0, bias=0.0, ece=0.0,
                abstention_rate=1.0 if not scores else 0.0,
            )
            continue

        lo, hi = band
        in_band = [lo <= s.score <= hi for s in scores]
        target = (lo + hi) / 2
        errors = [s.score - target for s in scores]

        per_category[cat_id] = CategoryCalibration(
            category=cat_id,
            n=len(scores),
            agreement_rate=sum(in_band) / len(scores),
            mean_absolute_error=sum(abs(e) for e in errors) / len(errors),
            bias=sum(errors) / len(errors),
            ece=_expected_calibration_error(scores, in_band, n_bins=n_bins),
            abstention_rate=sum(
                1 for s in scores if s.confidence < abstain_below
            ) / len(scores),
        )

    n = sum(c.n for c in per_category.values())
    if n == 0:
        return RiskCalibrationReport(0.0, 100.0, 1.0, per_category)

    return RiskCalibrationReport(
        overall_agreement=sum(
            c.agreement_rate * c.n for c in per_category.values()
        ) / n,
        overall_mae=sum(
            c.mean_absolute_error * c.n for c in per_category.values()
        ) / n,
        overall_ece=sum(
            c.ece * c.n for c in per_category.values()
        ) / n,
        per_category=per_category,
    )


def _expected_calibration_error(
    scores: Sequence[RiskScore],
    in_band: Sequence[bool],
    *,
    n_bins: int,
) -> float:
    if not scores:
        return 0.0
    bins: list[list[tuple[float, bool]]] = [[] for _ in range(n_bins)]
    for s, ok in zip(scores, in_band, strict=False):
        idx = min(int(s.confidence * n_bins), n_bins - 1)
        bins[idx].append((s.confidence, ok))

    n = len(scores)
    ece = 0.0
    for b in bins:
        if not b:
            continue
        mean_conf = sum(c for c, _ in b) / len(b)
        accuracy = sum(1 for _, ok in b if ok) / len(b)
        ece += (len(b) / n) * abs(mean_conf - accuracy)
    return ece


THRESHOLDS = {
    "overall_agreement": 0.75,
    "overall_mae": 18.0,
    "overall_ece": 0.10,
    "per_category_agreement": 0.65,
    "bias_magnitude": 12.0,
}


def failures(report: RiskCalibrationReport) -> list[str]:
    out: list[str] = []
    if report.overall_agreement < THRESHOLDS["overall_agreement"]:
        out.append(
            f"risk_calibration.overall_agreement {report.overall_agreement:.3f} "
            f"< {THRESHOLDS['overall_agreement']}"
        )
    if report.overall_mae > THRESHOLDS["overall_mae"]:
        out.append(
            f"risk_calibration.overall_mae {report.overall_mae:.1f} "
            f"> {THRESHOLDS['overall_mae']}"
        )
    if report.overall_ece > THRESHOLDS["overall_ece"]:
        out.append(
            f"risk_calibration.overall_ece {report.overall_ece:.3f} "
            f"> {THRESHOLDS['overall_ece']}"
        )
    for cat, c in report.per_category.items():
        if c.n == 0:
            out.append(f"risk_calibration.{cat}: no scores produced")
            continue
        if c.agreement_rate < THRESHOLDS["per_category_agreement"]:
            out.append(
                f"risk_calibration.{cat}.agreement {c.agreement_rate:.3f} "
                f"< {THRESHOLDS['per_category_agreement']}"
            )
        if abs(c.bias) > THRESHOLDS["bias_magnitude"]:
            direction = "over" if c.bias > 0 else "under"
            out.append(
                f"risk_calibration.{cat}.bias {c.bias:+.1f} "
                f"({direction}-scores by {abs(c.bias):.1f} pts)"
            )
    return out


def explain(c: CategoryCalibration) -> str:
    """One sentence, three audiences."""
    if c.n == 0:
        return f"{c.category}: no scores produced — coverage gap, not a pass."
    direction = "over" if c.bias > 0.5 else "under" if c.bias < -0.5 else "in line"
    return (
        f"{c.category}: {c.agreement_rate:.0%} of scores in analyst band "
        f"(MAE {c.mean_absolute_error:.0f} pts, {direction} by {abs(c.bias):.0f}); "
        f"confidence calibration ECE {c.ece:.2f}."
    )