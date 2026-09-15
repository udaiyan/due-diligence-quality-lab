from datetime import datetime

from ddql.evals.metrics.source_quality import coverage, source_quality
from ddql.types import Claim, Source


def _s(id_: str, tier: int) -> Source:
    return Source(id=id_, url="https://x", tier=tier, retrieved_at=datetime.now())


def test_source_quality_salience_weighted():
    claims = [
        Claim(id="a", text="x", citation_ids=("s1",), salience=1.0),
        Claim(id="b", text="y", citation_ids=("s2",), salience=0.1),
    ]
    sources = [_s("s1", 1), _s("s2", 4)]
    q = source_quality(claims, sources)
    # (1.0 * 1.0 + 0.1 * 3.0) / 1.1 = 1.3/1.1
    assert abs(q - (1.3 / 1.1)) < 1e-9


def test_coverage_distribution():
    sources = [_s("a", 1), _s("b", 1), _s("c", 4)]
    dist = coverage(sources)
    assert abs(dist["tier_1_share"] - 2 / 3) < 1e-9
    assert abs(dist["tier_4_share"] - 1 / 3) < 1e-9