"""Selector sync.

When an E2E test fails with SELECTOR_DRIFT, propose a selector update as a PR.
The human reviews the *semantic* question ("is this still the right element?"),
not the mechanical one.

Claude reads the trace and the DOM diff and proposes. The human answers the
one question Claude cannot: whether the new element means the same thing as
the old one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class SelectorSyncProposal:
    test_id: str
    old_selector: str
    new_selector: str
    semantic_question: str
    evidence: str


class ProposalBackend(Protocol):
    def propose(
        self, *, test_id: str, trace: str, dom_diff: str, old_selector: str
    ) -> dict[str, Any]: ...

def propose_selector_sync(
    *,
    test_id: str,
    trace: str,
    dom_diff: str,
    old_selector: str,
    backend: ProposalBackend,
) -> SelectorSyncProposal:
    raw = backend.propose(
        test_id=test_id, trace=trace, dom_diff=dom_diff, old_selector=old_selector,
    )
    return SelectorSyncProposal(
        test_id=test_id,
        old_selector=old_selector,
        new_selector=raw["new_selector"],
        semantic_question=(
            f"Does `{raw['new_selector']}` still represent the same element as "
            f"`{old_selector}` did? Claude found the match; only a human can "
            f"confirm the meaning."
        ),
        evidence=raw.get("evidence", ""),
    )