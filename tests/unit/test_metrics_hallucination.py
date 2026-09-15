from ddql.evals.metrics.hallucination import hallucination
from ddql.types import Claim, ClaimVerdict


def _c(id_: str) -> Claim:
    return Claim(id=id_, text="x", citation_ids=("s1",))


def test_hallucination_splits_unsupported_from_contradicted():
    claims = [_c("a"), _c("b"), _c("c")]
    verdicts = [
        ClaimVerdict(claim_id="a", supported=True, contradicted=False, confidence=1.0),
        ClaimVerdict(claim_id="b", supported=False, contradicted=False, confidence=1.0),
        ClaimVerdict(claim_id="c", supported=False, contradicted=True, confidence=1.0),
    ]
    r = hallucination(claims, verdicts)
    assert r.unsupported_rate == 1 / 3
    assert r.contradicted_rate == 1 / 3


def test_hallucination_missing_verdict_counts_as_unsupported():
    claims = [_c("a")]
    r = hallucination(claims, [])
    assert r.unsupported_rate == 1.0