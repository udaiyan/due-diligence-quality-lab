"""Smoke tests for the harness with L0+L1 only. No LLM calls."""

from __future__ import annotations

import pytest

from ddql.evals.harness import Harness
from ddql.evals.layers import L0Deterministic, L1Automated
from ddql.types import EvalCase, Segment, Verdict


@pytest.mark.eval
@pytest.mark.smoke
def test_smoke_happy_path(happy_output):
    case = EvalCase(
        id="smoke-1",
        query="Check Northwind",
        tenant="tenant-uk",
        segment=Segment.CORPORATE,
        risk_framework_id="corporate_supplier@v2",
        rubric_id="groundedness@v3.1",
        expected_entities=happy_output.entities,
        expected_source_tiers={"companies_house": "1"},
        expected_risk_bands={c: (0, 40) for c in
                             ("integrity", "esg", "cybersecurity", "financial",
                              "geopolitical", "quality", "business_continuity")},
        expected_timeline_event_ids=("evt-1",),
        tags=(),
    )
    h = Harness([L0Deterministic(), L1Automated()])
    report = h.run_case(case, happy_output, dataset_hash="sha256:test")
    assert report.verdict in (Verdict.PASS, Verdict.TAINTED), report.failures
    assert "L0" in report.layers_run
    assert "L1" in report.layers_run