"""LLM-as-judge.

The judge is an ensemble of one primary + one adversarial critic. The critic's
job is to find a reading under which the primary is wrong. If the critic
succeeds, confidence drops.

A single judge is a green tick that might be lying; an ensemble with a critic
is a green tick that has been argued with.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

from ddql.evals.judges.rubric import GROUNDEDNESS_V3_1, Rubric
from ddql.types import Claim, ClaimVerdict, Source


class JudgeBackend(Protocol):
    def score(
        self, *, prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class JudgeConfig:
    primary_model: str = "claude-sonnet-4-5"
    critic_model: str = "claude-sonnet-4-5"
    abstain_below: float = 0.55
    agreement_above: float = 0.80


class NullBackend:
    """Returns neutral scores. Used when no API key is configured."""

    def score(
        self, *, prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        return {"score": 0.5, "confidence": 0.0, "rationale": "null backend"}


class AnthropicBackend:
    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        import anthropic
        self._client = anthropic.Anthropic()
        self._model = model

    def score(
        self, *, prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text
        result: dict[str, Any]
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if not isinstance(parsed, dict):
            result = {"score": 0.5, "confidence": 0.0, "rationale": "parse failure"}
        else:
            result = parsed
        result.setdefault("model", self._model)
        return result

def build_default_judge() -> LLMJudge | None:
    """Reads DDQL_JUDGE env var. Returns None if no judge is configured —
    L2 then records a taint rather than failing."""
    backend_kind = os.environ.get("DDQL_JUDGE", "").lower()
    if backend_kind == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
        return LLMJudge(AnthropicBackend(), GROUNDEDNESS_V3_1)
    if backend_kind == "null":
        return LLMJudge(NullBackend(), GROUNDEDNESS_V3_1)
    return None


class LLMJudge:
    def __init__(
        self,
        backend: JudgeBackend,
        rubric: Rubric,
        config: JudgeConfig | None = None,
    ) -> None:
        self._backend = backend
        self._rubric = rubric
        self._config = config or JudgeConfig()

    def judge_claim(self, claim: Claim, sources: dict[str, Source]) -> ClaimVerdict:
        cited = [sources[sid] for sid in claim.citation_ids if sid in sources]

        if not cited:
            return ClaimVerdict(
                claim_id=claim.id,
                supported=False,
                contradicted=False,
                confidence=1.0,
                rationale="no citations attached",
                judge_id=f"{self._rubric.ref}+nocite",
            )

        primary = self._call(self._config.primary_model, claim, cited, role="primary")
        critic = self._call(self._config.critic_model, claim, cited, role="critic")

        agreement = 1.0 - abs(primary["score"] - critic["score"])
        supported = primary["score"] >= 0.5 and critic["score"] >= 0.5
        contradicted = (
            (1.0 - primary["score"]) >= 0.5 and (1.0 - critic["score"]) >= 0.5
        )
        confidence = (primary["confidence"] + critic["confidence"]) / 2 * agreement

        rationale = primary["rationale"]
        if agreement < self._config.agreement_above:
            rationale = (
                f"[disagreement {agreement:.2f}] primary: {primary['rationale']} "
                f"| critic: {critic['rationale']}"
            )

        if confidence < self._config.abstain_below:
            rationale = f"[abstain→L3] {rationale}"

        return ClaimVerdict(
            claim_id=claim.id,
            supported=supported,
            contradicted=contradicted,
            confidence=confidence,
            rationale=rationale,
            judge_id=(
                f"{self._rubric.ref}+{primary.get('model', '?')}+"
                f"{critic.get('model', '?')}"
            ),
        )

    def _call(
        self,
        model: str,
        claim: Claim,
        cited: list[Source],
        *,
        role: str,
    ) -> dict[str, Any]:
        prompt = self._build_prompt(claim, cited, role=role)
        schema = {
            "type": "object",
            "properties": {
                "score": {"type": "number"},
                "confidence": {"type": "number"},
                "rationale": {"type": "string"},
            },
            "required": ["score", "confidence", "rationale"],
        }
        raw = self._backend.score(prompt=prompt, schema=schema)
        raw.setdefault("model", model)
        return raw

    def _build_prompt(
        self, claim: Claim, cited: list[Source], *, role: str
    ) -> str:
        dims = "\n".join(
            f"- {d.id} (weight {d.weight}): {d.question} Fail if: {d.fail_if}"
            for d in self._rubric.dimensions
        )
        sources = "\n\n".join(
            f"[{s.id}] tier={s.tier} publisher={s.publisher}\n{s.url}"
            for s in cited
        )
        stance = (
            "You are a careful, sceptical evaluator. Score the claim honestly."
            if role == "primary"
            else (
                "You are an adversarial critic. Your job is to find a defensible "
                "reading under which the claim is NOT supported. Only score high "
                "if you genuinely cannot."
            )
        )
        return (
            f"{stance}\n\n"
            f"Rubric: {self._rubric.ref}\n{dims}\n\n"
            f"Claim: {claim.text}\n\n"
            f"Cited sources:\n{sources}\n\n"
            "Return JSON: {score: 0-1, confidence: 0-1, rationale: str}.\n"
            "score = weighted support across the rubric dimensions."
        )