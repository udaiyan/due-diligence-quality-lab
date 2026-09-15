from ddql.evals.metrics.groundedness import (
    abstention_rate,
    groundedness,
    per_dimension_rollup,
)
from ddql.types import Claim, ClaimVerdict


def _c(id_: str, salience: float = 1.0) -> Claim:
    return Claim(id=id_, text="x", citation_ids=("s1",), salience=salience)


def _v(id_: str, supported: bool, confidence: float = 1.0) -> ClaimVerdict:
    return ClaimVerdict(
        claim_id=id_, supported=supported, contradicted=False, confidence=confidence
    )


def test_groundedness_all_supported():
    claims = [_c("a"), _c("b")]
    verdicts = [_v("a", True), _v("b", True)]
    assert groundedness(claims, verdicts) == 1.0


def test_groundedness_salience_weighted():
    claims = [_c("high", 1.0), _c("low", 0.1)]
    verdicts = [_v("high", True), _v("low", False)]
    # 1.0 / 1.1
    assert abs(groundedness(claims, verdicts) - (1.0 / 1.1)) < 1e-9


def test_groundedness_empty_is_zero():
    assert groundedness([], []) == 0.0


def test_abstention_rate():
    verdicts = [_v("a", True, 0.9), _v("b", True, 0.3)]
    assert abstention_rate(verdicts) == 0.5


def test_per_dimension_rollup_bands():
    claims = [_c("h", 0.9), _c("m", 0.5), _c("l", 0.1)]
    verdicts = [_v("h", True), _v("m", True), _v("l", False)]
    out = per_dimension_rollup(claims, verdicts)
    assert out["groundedness_high_salience"] == 1.0
    assert out["groundedness_mid_salience"] == 1.0
    assert out["groundedness_low_salience"] == 0.0