"""Fixtures for the eval-harness smoke tests."""

from __future__ import annotations

import pytest

from ddql.types import (
    Claim,
    Entity,
    InvestigationOutput,
    RiskScore,
    Segment,
    Severity,
    Source,
    TimelineEvent,
)
from datetime import date, datetime


@pytest.fixture
def happy_output() -> InvestigationOutput:
    return InvestigationOutput(
        case_id="smoke-1",
        tenant="tenant-uk",
        segment=Segment.CORPORATE,
        risk_framework_id="corporate_supplier@v2",
        executive_summary="Northwind Holdings Ltd is clean.",
        claims=(
            Claim(id="cl1", text="Northwind is UK-registered.", citation_ids=("src1",), salience=1.0),
            Claim(id="cl2", text="No sanctions found.", citation_ids=("src1",), salience=0.8, risk_category="sanctions"),
        ),
        entities=(
            Entity(name="Northwind Holdings Ltd", kind="org", identifiers={"companies_house": "09876543"}),
        ),
        sources=(
            Source(id="src1", url="https://find-and-update.company-information.service.gov.uk/company/09876543",
                   tier=1, retrieved_at=datetime(2026, 3, 20), published_at=datetime(2026, 1, 1),
                   publisher="Companies House"),
        ),
        risk_scores=tuple(
            RiskScore(category=c, score=20.0, severity=Severity.LOW, confidence=0.9,
                      rationale="no concerns", citation_ids=("src1",))
            for c in ("integrity", "esg", "cybersecurity", "financial",
                      "geopolitical", "quality", "business_continuity")
        ),
        timeline=(
            TimelineEvent(id="evt-1", description="Incorporated",
                          date=date(2015, 5, 12), date_precision="day",
                          event_type="incorporation", citation_ids=("src1",)),
        ),
    )