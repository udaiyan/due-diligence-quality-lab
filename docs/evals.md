# Evals

## The shape of the problem

A normal test suite asks "did the output equal the expected output?" That
question is meaningless for investigative output. The same correct answer can
be worded a hundred ways, and the same wording can be right or catastrophically
wrong depending on whether the citations actually support it.

So we don't test outputs. We test **properties of outputs**, at four
increasingly expensive layers, and we track six signals over time.

## The four layers

### L0 — Deterministic

Cheapest. Asks: is the output well-formed? Does every claim carry at least one
citation? Are all cited source IDs present in the source list? Does every
framework category have a score? Is any sanctions assertion supported by a
primary-tier source?

No LLM. Runs in milliseconds. A case that fails L0 never reaches L2.

### L1 — Automated

Also no LLM. Asks: do the entities match the golden expected entities? Are
the sources tiered as expected? Are the risk scores in band? Is the timeline
in order and are all expected events present?

Milliseconds per case. Catches drift, substitution, and out-of-band scoring.

### L2 — LLM-as-judge

The expensive layer. Asks: is each claim **entailed** by its cited sources,
per the active rubric?

Runs a primary judge and an adversarial critic. If they disagree, confidence
drops. If confidence drops below threshold, the claim routes to L3 as an
abstention.

### L3 — Human review

Sampled + disagreement-driven. Humans adjudicate where L1 and L2 disagree,
and where the judge abstained. Every human verdict feeds back into L2's
calibration set.

## The six signals

| Signal | What it answers |
|---|---|
| **Groundedness** | Fraction of claim salience supported by citations |
| **Hallucination** | Split into unsupported (gap) and contradicted (lie) |
| **Entity resolution** | P/R/F1 + disambiguation accuracy + transliteration F1 + ECE |
| **Source quality** | Salience-weighted mean tier; tier distribution |
| **Risk calibration** | Per-category agreement with analysts + bias + ECE |
| **Timeline** | Ordering, completeness, precision honesty, anachronism rate |

Each has a threshold, a drift tolerance, and a plain-English explanation.

## The verdicts

- **PASS** — every signal in band, dataset hash matches baseline.
- **TAINTED** — signals in band, but something upstream degraded.
- **FAIL** — a hard threshold was breached.

See ADR-003 for why TAINTED exists.

## Adding a metric

1. New module in `src/ddql/evals/metrics/<name>.py`
2. Function taking the relevant slices of `InvestigationOutput`
3. `THRESHOLDS` dict
4. `failures(...)` returning `list[str]`
5. `explain(...)` returning one sentence
6. Unit test in `tests/unit/test_metrics_<name>.py`
7. Wire into the layer that owns it (`L1` for deterministic, `L2` for judge-dependent)
8. Update this doc