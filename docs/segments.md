# Segments and why the evals are segment-aware

A single global metric on a due-diligence platform is a lie of averages.

The 2026-03-07 incident proved this: Arabic→Latin transliteration recall
dropped from 0.97 to 0.88 across the MENA cohort after an unrelated resolver
change. The global entity-resolution number moved from 0.961 to 0.958 — well
inside any reasonable drift tolerance. Every dashboard was green. The MENA
cohort was failing one in eight cases.

We only caught it because a golden case tagged `transliteration` failed and
someone had the sense to look at the tag distribution rather than the mean.

## What segment-aware means in practice

Every `EvalCase` carries a `segment` and a `risk_framework_id`. Every metric
rolls up globally and per segment. Every threshold has both a global floor
and a per-segment floor, and both must pass.

```python
summarise_by_segment(reports)["university"]["mean_entity_resolution.same_name_accuracy"]
# → 0.79  ← this is the number that matters for the university cohort
```

The global number is still published. It is not still the gate.

## The six segments and what "risk" means for each

**Law firms.** Entity is an incoming client. Risk is sanctions exposure, PEP
status, adverse media across jurisdictions, and whether the stated source of
wealth is supported. Framework: `law_firm_client`.

**Private banks.** Entity is a high-net-worth client. Risk is whether the
stated biography is real — education, career, business associations,
philanthropy — and whether it supports the stated source of wealth. Framework:
`private_bank_hnw`.

**Universities.** Entity is a donor or research partner. Risk is
reputational: would accepting this gift attract credible public criticism?
Does it conflict with the institution's gift-acceptance policy? Framework:
`university_donor`.

**Nonprofits.** Entity is a donor. Narrower than universities — the
charity's gift-acceptance policy is the dominant constraint, and "research
integrity" doesn't apply. Framework: `nonprofit_donor`.

**Corporates.** Entity is a supplier or third party. The framework has
seven risk categories: integrity, ESG, cybersecurity, financial, geopolitical,
quality, business continuity. Framework: `corporate_supplier`.

**Professional services.** Entity is a client, and the platform is often
being used at scale as a first-pass screen. Uses `law_firm_client` by default
but tenants can override.

## Why not one framework for all?

Because the same fact is different risk in different segments.

A 2019 environmental fine is a reputational concern for a university
considering a gift; it is an ESG concern for a supplier onboarding; it is
adverse media for a law firm client. The scoring question is different,
the weight is different, and the band a human analyst would give is different.

Collapsing these into one framework would either over-weight categories that
don't apply (a university doesn't care about business continuity) or
under-weight the ones that do (a bank cares a lot about PEP status; a charity
cares very little).

## How segment and framework interact in the eval

```text
EvalCase
  ├── segment: university
  ├── risk_framework_id: university_donor@v1
  └── expected_risk_bands: { reputational: (20, 45), sanctions: (0, 15), ... }
```

The harness loads the framework, checks every category is scored, checks each
score is in the expected band, and checks each score is justified by at least
one cited claim (L2). Failure at any of those is a FAIL; drift is a TAINT.

## What we are not doing

We are not building a segment classifier. Segment is asserted by the case
author, not inferred by the system.

We are not weighting segments by customer count. Every customer's failure is
a failure.


---

## `docs/flaky-tests.md`

````markdown
# Flaky tests

Most teams retry flaky tests. Retries hide bugs.

This repo classifies instead. `ddql.ci.flake_triage` takes a failure (test id,
trace, run history) and returns a `FlakeClass` with evidence and a suggested
action.

## The classes

| Class | Signal | Action |
|---|---|---|
| `SELECTOR_DRIFT` | Passes on previous commit, fails on this one, at the same selector | Autofile a selector-sync PR via Claude Code |
| `TIMING` | Intermittent, trace shows a race, element appeared after assertion | Explicit wait-for-condition, never a sleep |
| `DATA_STATE` | Passes alone, fails in full suite | Scope the fixture; file a bug if it leaked |
| `INFRA` | 5xx, DNS, connection reset | Flag, don't retry silently |
| `GENUINE_BUG` | AssertionError where the test is right and the app is wrong | Page the owning squad |
| `UNKNOWN` | None of the above | Escalate with trace. Never retry |

## Why `UNKNOWN` is never retried

An unclassified flake is a bug we haven't understood yet. Retrying it is how
you end up with a suite that passes 100% of the time and ships broken code.

The classifier only says `UNKNOWN` when the deterministic heuristics don't
match and no Claude backend is configured. With a backend, Claude proposes
a class and the human confirms or overrides.

## Overrides are training data

Every Claude suggestion a human overrides is logged with the trace. Overrides
become labelled examples. The classifier improves because people use it, not
because someone remembers to tune it.

## Integration

```bash
uv run python -m ddql.ci.flake_triage \
  --junit reports/junit-chromium-1.xml \
  --traces test-results/ \
  --autofile-issues
  
```

Runs automatically in T3 on failure. --autofile-issues creates GitHub issues
with the classification, evidence, and suggested action.
````

---

## `docs/claude-code-workflow.md`

````markdown
# Claude Code workflow

Claude Code is the default pair here, not a novelty. Three loops, each with a
human gate at the point where judgement — not mechanics — is required.

## 1. Selector sync

**Trigger:** T3 failure classified as `SELECTOR_DRIFT`.

**What Claude does:** reads the failing trace, the component diff between the
last green commit and HEAD, and the test file. Proposes a selector update as
a PR.

**What the human does:** answers one question — *is this still the
semantically correct element?* Claude can tell you the test-id moved. It
cannot tell you whether `run-investigation` should now point at the new
"Re-run" button. That's the craft.

**Guardrail:** selector-sync PRs are never auto-merged, even when CI is green.
The whole point of the exercise is that a green tick can be lying.

## 2. Failure triage

**Trigger:** any T3 failure not matched by the deterministic heuristics in
`flake_triage.py`.

**What Claude does:** summarises the trace into a `FlakeClass` suggestion with
evidence, which `flake_triage.py` either confirms or overrides.

**What the human does:** confirms or overrides the label. Overrides are logged
with the trace and become labelled examples.

**Guardrail:** `UNKNOWN` is never retried.

## 3. Eval scoring

**Trigger:** T2 golden eval.

**What Claude does:** drafts per-claim groundedness verdicts against the
active rubric. These are *candidates*.

**What the human does:** the L3 sample adjudicates. Claude's drafts are scored
against human verdicts monthly and the agreement number is published in
`RESULTS.md`. When agreement drops, the rubric gets a changelog entry — not
a prompt tweak.

**Guardrail:** Claude never sets the final verdict on a `high_salience` claim.
Those route to the ensemble judge plus a human, always.

## Why this shape

The failure mode of AI-assisted quality work is that the AI becomes the
oracle. Then you have a green tick with no one behind it, and you're back to
where you started, except faster.

The shape above puts Claude where it's strong (mechanical work, summarisation,
pattern matching against traces) and humans where they're strong (semantic
judgement, deciding what "degraded" means, knowing when to distrust the
number). The `TAINTED` verdict exists for the same reason.