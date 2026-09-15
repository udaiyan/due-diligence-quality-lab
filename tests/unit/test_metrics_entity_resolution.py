from ddql.evals.metrics.entity_resolution import entity_resolution
from ddql.types import Entity


def _e(name: str, wikidata: str | None = None) -> Entity:
    ids = {"wikidata": wikidata} if wikidata else {}
    return Entity(name=name, kind="person", identifiers=ids)


def test_perfect_match():
    e = [_e("A", "Q1"), _e("B", "Q2")]
    r = entity_resolution(e, e)
    assert r.f1 == 1.0
    assert r.ece == 0.0


def test_same_name_disambiguation():
    pred = [_e("John Smith", "Q100")]
    expected = [_e("John Smith", "Q100"), _e("John Smith", "Q200")]
    r = entity_resolution(pred, expected, case_tags=("same_name",))
    assert r.disambiguation.same_name_accuracy == 1.0


def test_same_name_wrong_pick():
    pred = [_e("John Smith", "Q999")]
    expected = [_e("John Smith", "Q100")]
    r = entity_resolution(pred, expected, case_tags=("same_name",))
    assert r.disambiguation.same_name_accuracy == 0.0