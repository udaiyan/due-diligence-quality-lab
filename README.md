# Due Diligence Quality Lab

> **The craft is knowing when a green tick is lying.**

Quality infrastructure for a due-diligence platform where the output is a
**risk report** — entities, claims, citations, risk scores, and a timeline —
assembled by a non-deterministic system from open sources and structured
compliance data.

This is not a generic LLM eval harness. The interesting problems here are
specific to investigative output: entity disambiguation at scale, groundedness
on prose that reads as authoritative regardless of whether it is, risk-score
calibration against human analysts, and timeline reconstruction where a
correctly-grounded but out-of-order event is still wrong.

---

## What this repo assumes about the domain

The output under test is a **structured risk report**, not a chatbot reply.
That assumption drives every design choice in the codebase.

**Six customer segments**, each asking a different risk question:

| Segment | Entity under investigation | What "risk" means |
|---|---|---|
| **Law firms** | Incoming clients | Sanctions, PEPs, source of wealth, AML/ABC/ESG |
| **Private banks** | HNW clients | Background, career, business associations, philanthropy |
| **Universities** | Donors, research partners | Reputational, gift acceptance, research integrity |
| **Nonprofits** | Donors | Reputational, gift acceptance, sanctions exposure |
| **Corporates** | Suppliers, third parties | Integrity, ESG, cybersecurity, financial, geopolitical, quality, business continuity |
| **Professional services** | Clients | Onboarding at scale |

**The output has structure.** Executive summary, entity list, claim set with
citations, risk scores per framework category, and a timeline. Each of those
is a first-class eval target, not a derived signal.

**Entity disambiguation is the product.** Treating "did you find the entity?"
as a binary question misses the failure mode that matters: picking the *wrong*
entity with the *right* name.

**Anti-hallucination is a product requirement.** Not a nicety. The
hallucination metric is a gate.

---

## How this maps to a quality engineer role

| Typical requirement | Where it lives | Proof |
|---|---|---|
| Enhance & run layered eval harnesses | `src/ddql/evals/harness.py`, `layers.py` | 4 layers: deterministic → automated → LLM-judge → human review |
| LLM-as-judge scoring, rubrics | `src/ddql/evals/judges/` | Rubrics are versioned data, not prompt strings |
| Versioned golden datasets | `src/ddql/evals/datasets/`, `datasets/golden/` | Content-hashed manifests; every report pins a dataset hash |
| Groundedness, hallucination, entity resolution, source quality | `src/ddql/evals/metrics/` | Six signals, each with thresholds, drift tolerance, plain-English explain |
| Tiered CI on Python + Playwright + pytest | `.github/workflows/`, `tests/e2e/` | 6 personas × 3 browsers × multi-tenant |
| Dig into flaky tests, fix at root | `src/ddql/ci/flake_triage.py`, `docs/flaky-tests.md` | Classifier + issue autofiler, not a retry loop |
| Claude Code by default | `CLAUDE.md`, `docs/claude-code-workflow.md` | Selector sync, failure triage, eval scoring |
| Make complex things simple | This README, `RESULTS.md` | Same metric explained for engineer / analyst / customer lead |
| Analytically sceptical, numerate | `Verdict.TAINTED`, `risk_calibration.calibration` | A green tick can be tainted — see ADR-003 |
| Genuinely interested in AI quality | `docs/evals.md`, `docs/segments.md` | The whole repo is the answer |

---

## The four layers

| Layer | Asks | Cost | Catches |
|---|---|---|---|
| **L0** | Schema, citation presence, framework coverage, sanctions source-tier | ~1ms | Broken output shape |
| **L1** | Entities match golden, sources tiered, risk bands, timeline ordering | ~50ms | Drift, substitution, out-of-band scoring |
| **L2** | LLM-judge: is each claim entailed by its cited source? | ~2s | Confident fabrication, unjustified scoring |
| **L3** | Human adjudication, sampled + disagreement-driven | minutes | Judge blind spots, rubric gaps |

---

## The six signals

| Signal | Definition | Math | Module |
|---|---|---|---|
| **Groundedness** | Salience-weighted fraction of claims supported | `Σ(sal × supported) / Σ(sal)` | `metrics/groundedness.py` |
| **Hallucination** | Split into `unsupported_rate` and `contradicted_rate` | see module | `metrics/hallucination.py` |
| **Entity resolution** | P/R/F1 + **disambiguation accuracy** + transliteration F1 + ECE | see module | `metrics/entity_resolution.py` |
| **Source quality** | Salience-weighted mean tier; tier distribution | `Σ(sal × tier) / Σ(sal)` | `metrics/source_quality.py` |
| **Risk calibration** | Per-category agreement with analysts + bias + ECE | see module | `metrics/risk_calibration.py` |
| **Timeline** | Ordering, completeness, precision honesty, anachronism rate | see module | `metrics/timeline.py` |

---

## Segment-aware golden data

A single golden set hides segment-specific regressions. A Latin-script-only
golden set would report healthy entity-resolution numbers while a
transliteration cohort quietly failed at 12%.

Every metric rolls up **globally and per segment**. A PR that drops one
segment's entity resolution by 12 points fails even if the global number is
flat. See ADR-004.

---

## Claude Code workflow

Three loops, each with a human gate at the judgement point:

1. **Selector sync** — `SELECTOR_DRIFT` failures autofile a PR; the human
   answers "is this still the semantically correct element?"
2. **Failure triage** — `flake_triage.py` classifies; Claude is the tiebreaker
   for `UNKNOWN`; overrides become labelled examples.
3. **Eval scoring** — Claude drafts per-claim groundedness verdicts. A human
   L3 sample adjudicates. Agreement is published monthly in `RESULTS.md`.

See `CLAUDE.md` for conventions Claude Code follows in this repo.

---

## What this caught

| Date | Signal | Movement | Verdict | Root cause | Fix |
|---|---|---|---|---|---|
| 2026-03-02 | groundedness | 0.94 → 0.81 | FAIL | Citation mapper dropped footnotes on multi-page PDFs | Parser fix + 12 multi-page golden cases |
| 2026-03-07 | entity_resolution (recall, MENA) | 0.97 → 0.88 | FAIL | Arabic→Latin transliteration regression | Golden set expanded to 60 transliteration pairs |
| 2026-03-11 | source_quality | 2.1 → 2.9 | **TAINTED** | Primary registry timeouts → silent aggregator fallback | Timeout + circuit breaker + `tier_1_share` gate |
| 2026-03-14 | hallucination (contradicted) | 0.002 → 0.019 | FAIL | Judge prompt drift after rubric v3 edit | Rubric v3.1 + judge recalibration |
| 2026-03-18 | risk_calibration (integrity) | ECE 0.06 → 0.14 | FAIL | Framework v2 reweighting not reflected in judge rubric | Judge rubric v2.1 + 40 analyst-labelled cases |
| 2026-03-21 | timeline (ordering) | 0.96 → 0.79 | TAINTED | Undated events sorted by ingestion time | Sort policy + `undated_rate` gate |

Six regressions a pass/fail suite would have shipped. Two are only visible
because the metrics are segment-aware and framework-aware.

---

## Quick start

```bash
git clone https://github.com/<you>/due-diligence-quality-lab
cd due-diligence-quality-lab
uv sync

uv run pytest tests/unit
uv run pytest tests/eval -m smoke

DDQL_JUDGE=anthropic uv run python scripts/run_eval.py \
  --dataset datasets/golden/v2 \
  --layers L0,L1,L2 \
  --report reports/$(date +%F).json
```

---

## Design decisions

- **ADR-001** — Four layers, not one big eval
- **ADR-002** — Golden datasets are content-hashed and versioned like code
- **ADR-003** — `TAINTED` exists between `PASS` and `FAIL`
- **ADR-004** — Segment-aware evals, because aggregate metrics hide cohort regressions

---

*Built by a quality engineer who thinks the most interesting problem in AI
right now is **how you know when it's wrong**.*