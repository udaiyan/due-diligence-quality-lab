from ddql.evals.harness import Harness, summarise
from ddql.evals.layers import Layer, LayerResult
from ddql.types import EvalCase, InvestigationOutput, Segment, Verdict


class PassLayer:
    name = "PASS"
    def evaluate(self, case, output):
        return LayerResult(name=self.name, metrics={"x": 1.0})


class TaintLayer:
    name = "TAINT"
    def evaluate(self, case, output):
        return LayerResult(name=self.name, taints=["something degraded"])


class FailLayer:
    name = "FAIL"
    def evaluate(self, case, output):
        return LayerResult(name=self.name, failures=["hard failure"])


def _case() -> EvalCase:
    return EvalCase(
        id="c1", query="q", tenant="t", segment=Segment.CORPORATE,
        risk_framework_id="corporate_supplier@v2", rubric_id="groundedness@v3.1",
        expected_entities=(), expected_source_tiers={},
        expected_risk_bands={}, expected_timeline_event_ids=(),
    )


def _output() -> InvestigationOutput:
    return InvestigationOutput(
        case_id="c1", tenant="t", segment=Segment.CORPORATE,
        risk_framework_id="corporate_supplier@v2",
        executive_summary="", claims=(), entities=(), sources=(),
        risk_scores=(), timeline=(),
    )


def test_all_pass():
    h = Harness([PassLayer()])
    r = h.run_case(_case(), _output(), dataset_hash="sha256:abc")
    assert r.verdict == Verdict.PASS
    assert r.layers_run == ("PASS",)


def test_taint_not_fail():
    h = Harness([TaintLayer()])
    r = h.run_case(_case(), _output(), dataset_hash="sha256:abc")
    assert r.verdict == Verdict.TAINTED


def test_failure_short_circuits():
    h = Harness([FailLayer(), PassLayer()])
    r = h.run_case(_case(), _output(), dataset_hash="sha256:abc")
    assert r.verdict == Verdict.FAIL
    assert "PASS" in r.layers_skipped


def test_drift_becomes_taint():
    h = Harness([PassLayer()], baseline={"x": 2.0}, drift_tolerance=0.03)
    r = h.run_case(_case(), _output(), dataset_hash="sha256:abc")
    assert r.verdict == Verdict.TAINTED
    assert any("drift" in t for t in r.taints)


def test_summarise():
    h = Harness([PassLayer()])
    reports = [h.run_case(_case(), _output(), dataset_hash="sha256:abc")]
    s = summarise(reports)
    assert s["cases"] == 1
    assert s["pass"] == 1