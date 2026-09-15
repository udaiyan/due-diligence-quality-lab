# CLAUDE.md

Conventions for Claude Code when working in this repo.

## What this repo is

Quality infrastructure for a due-diligence platform. The output under test is
a **risk report** — entities, claims, citations, risk scores, timeline — not
a chatbot reply. Every metric here exists to catch a specific real failure
mode of that output.

## Rules

1. **Every non-obvious decision gets an ADR.** If you're about to make a
   choice a future engineer would question, write it down first.
2. **Every metric has three things:** a threshold, a drift tolerance, and a
   plain-English explanation for a non-engineer. If you can't write the third,
   the metric isn't ready.
3. **Golden data is content-hashed.** Never edit `cases.jsonl` without bumping
   the hash in `manifest.json`. The loader will refuse to run.
4. **Flakes are classified, never retried.** If a test fails, run
   `ddql.ci.flake_triage` before touching anything.
5. **`TAINTED` is a real verdict.** Do not collapse it into `PASS` or `FAIL`.
6. **Segment every metric.** Global rollups hide cohort regressions.
7. **Risk scores are framework-conditional.** Do not write a metric that
   assumes a universal set of risk categories.

## When asked to...

**...fix a flaky test:** classify it first with `ddql.ci.flake_triage`.
`UNKNOWN` is never retried — escalate with the trace.

**...add a metric:** put it in `metrics/`, write a threshold, write a
human-facing explanation, add a unit test, update `docs/evals.md`.

**...update a rubric:** bump the version. Add a changelog entry. Recalibrate
the judge against the L3 human sample before merging.

**...add a golden case:** add it to the current version directory. Bump the
manifest hash. Tag with the correct `segment` and `risk_framework_id`.

**...touch the E2E suite:** use `data-testid` selectors only. If a selector
moved, the fix is a selector-sync PR with human review of the semantic
question, not a CSS path change.

## What not to do

- Do not add a metric without a threshold.
- Do not add a threshold without a human-facing explanation.
- Do not merge a rubric change without a version bump.
- Do not auto-merge a selector-sync PR, even if CI is green.
- Do not write a test that asserts on exact prose. Assert on properties.