# Architecture

## Dataflow

EvalCase ─┐
├──► Harness ──► Layer[0..N] ──► CaseReport ──► Report (JSON / MD)
Output ─┘ │
├── L0 schema, citations, framework coverage
├── L1 entities, sources, risk bands, timeline
├── L2 LLM-as-judge on claims
└── L3 human verdict fixture (sampled)


## Layering rules

1. **Cheap → expensive.** L0 is ~1ms, L2 is ~2s per claim. A case that fails
   L0 never reaches L2.
2. **Independent.** Each layer receives the same `(case, output)` pair and
   returns a `LayerResult`. No layer sees another's internals.
3. **Short-circuit on failure.** A failing layer stops the pipeline. Taints
   do not stop the pipeline.
4. **Short-circuit is visible.** `CaseReport.layers_run` and
   `layers_skipped` record exactly what ran.

## Report provenance

Every `CaseReport` embeds:

- `dataset_hash` — content hash of the golden set this case came from. Two
  reports with different hashes are not comparable, and the report says so.
- `layers_run` / `layers_skipped` — the exact pipeline the case went through.
- `taints` — reasons a human should look even though thresholds passed.
- `failures` — reasons the case failed.

A report without these is not evidence.

## Where new metrics go

`src/ddql/evals/metrics/<name>.py`, with:

- A function that takes the relevant slices of `InvestigationOutput`
- A `THRESHOLDS` dict
- A `failures(...)` function returning `list[str]`
- An `explain(...)` function returning one human-readable sentence
- A unit test in `tests/unit/test_metrics_<name>.py`

Then wire it into the layer that owns it (`layers.py`). L1 for deterministic,
L2 for judge-dependent.

## Why segments

Aggregate metrics hide cohort regressions. See `docs/segments.md` and ADR-004.
Every metric rolls up globally and per segment, and both must pass.