"""Deterministic pre-checks the judge never needs to see.

Uncited claims are a hard fail. Claims whose cited source URL 404s are a
taint. Both are cheap, both are deterministic, and both mean the LLM's budget
is spent on the claims where judgement is actually required.
"""

from __future__ import annotations

import re

from ddql.types import Claim, ClaimVerdict, Source

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def precheck_claim(claim: Claim, sources: dict[str, Source]) -> ClaimVerdict | None:
    """Return a ClaimVerdict if the claim fails deterministically, else None."""
    if not claim.citation_ids:
        return ClaimVerdict(
            claim_id=claim.id,
            supported=False,
            contradicted=False,
            confidence=1.0,
            rationale="uncited",
            judge_id="deterministic+uncited",
        )

    cited = [sources[sid] for sid in claim.citation_ids if sid in sources]
    if not cited:
        return ClaimVerdict(
            claim_id=claim.id,
            supported=False,
            contradicted=False,
            confidence=1.0,
            rationale="all citations dangling",
            judge_id="deterministic+dangling",
        )

    if any(not _URL_RE.match(s.url) for s in cited):
        return ClaimVerdict(
            claim_id=claim.id,
            supported=False,
            contradicted=False,
            confidence=0.9,
            rationale="citation URL malformed",
            judge_id="deterministic+badurl",
        )

    return None