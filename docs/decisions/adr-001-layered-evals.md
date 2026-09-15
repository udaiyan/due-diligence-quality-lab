# ADR-001: Four layers, not one big eval

**Status:** Accepted
**Date:** 2026-01-15

## Context

The first eval suite was a single pytest file that ran an LLM judge over every
case. It cost $40 per run, took 45 minutes, and told us almost nothing about
*why* a case failed.

## Decision

Four layers, run in order of increasing cost:

- **L0** — deterministic schema and coverage checks (~1ms)
- **L1** — entity resolution, source tiering, risk bands, timeline (~50ms)
- **L2** — LLM-as-judge on claims (~2s/claim)
- **L3** — human review (minutes)

A case that fails L0 never reaches L2. A case that fails L1 never reaches L2.
Every layer reports what it checked and what it skipped.

## Consequences

**Good.** Cost dropped 20× because L2 only runs on cases that survive L0+L1.

**Good.** Failures now say *what kind of failure* they are. An uncited claim
is different from an ungrounded claim.

**Good.** Layers are independently testable. L0 and L1 have no LLM dependency
and run in normal CI without an API key.

**Cost.** More files, more indirection. A trivial "add an assertion" change
now requires deciding which layer owns it.

**Cost.** Cases that fail L0 give us no signal about L2. This is by design,
but it means a wave of L0 failures hides whatever L2 would have said.

## What we considered and rejected

**One layer, run everything.** Simpler to write, 20× more expensive, and
"groundedness is 0.7" with no breakdown is not actionable.

**Two layers: deterministic and judged.** Too coarse. Entity resolution and
risk bands are deterministic but produce signals the judge cannot, and
grouping them with schema checks would hide their independent thresholds.