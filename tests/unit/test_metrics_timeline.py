from datetime import date

from ddql.evals.metrics.timeline import evaluate_timeline
from ddql.types import TimelineEvent


def _e(id_: str, d: date | None) -> TimelineEvent:
    return TimelineEvent(
        id=id_, description="x", date=d,
        date_precision="day" if d else "unknown",
        event_type="x", citation_ids=(),
    )


def test_in_order():
    events = [
        _e("a", date(2019, 1, 1)),
        _e("b", date(2020, 1, 1)),
        _e("c", date(2021, 1, 1)),
    ]
    r = evaluate_timeline(events, expected_event_ids=("a", "b", "c"), sources=[])
    assert r.ordering_accuracy == 1.0
    assert r.undated_rate == 0.0


def test_out_of_order():
    events = [
        _e("b", date(2020, 1, 1)),
        _e("a", date(2019, 1, 1)),
    ]
    r = evaluate_timeline(events, expected_event_ids=("a", "b"), sources=[])
    assert r.ordering_accuracy < 1.0


def test_undated_rate():
    events = [_e("a", date(2020, 1, 1)), _e("b", None)]
    r = evaluate_timeline(events, expected_event_ids=("a", "b"), sources=[])
    assert r.undated_rate == 0.5