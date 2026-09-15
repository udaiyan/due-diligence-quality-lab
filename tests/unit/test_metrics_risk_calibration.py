from ddql.evals.metrics.risk_calibration import calibrate
from ddql.segments import CORPORATE_SUPPLIER_V2
from ddql.types import RiskScore, Severity


def _r(cat: str, score: float, conf: float = 0.9) -> RiskScore:
    return RiskScore(
        category=cat, score=score,
        severity=Severity.MEDIUM, confidence=conf,
        rationale="", citation_ids=(),
    )


def test_all_in_band():
    scores = [_r("integrity", 20), _r("esg", 15)]
    bands = {"integrity": (10, 30), "esg": (10, 25)}
    # pad missing categories so framework coverage doesn't cause zero
    for c in CORPORATE_SUPPLIER_V2.categories:
        if c.id not in {"integrity", "esg"}:
            scores.append(_r(c.id, 20))
            bands[c.id] = (10, 30)
    report = calibrate(scores, human_bands=bands, framework=CORPORATE_SUPPLIER_V2)
    assert report.overall_agreement == 1.0


def test_missing_category_is_failure():
    scores = [_r("integrity", 20)]
    bands = {"integrity": (10, 30)}
    report = calibrate(scores, human_bands=bands, framework=CORPORATE_SUPPLIER_V2)
    assert report.per_category["esg"].n == 0