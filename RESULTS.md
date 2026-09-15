# What this caught

Six regressions between 2026-03-02 and 2026-03-21. All six would have shipped
under a pass/fail suite. Each is a real failure mode of a non-deterministic
system, not a hypothetical.

| Date | Signal | Movement | Verdict | Root cause | Fix |
|---|---|---|---|---|---|
| 2026-03-02 | groundedness | 0.94 → 0.81 | FAIL | Citation mapper dropped footnotes on multi-page PDFs | Parser fix + 12 multi-page golden cases |
| 2026-03-07 | entity_resolution (recall, MENA) | 0.97 → 0.88 | FAIL | Arabic→Latin transliteration regression | Golden set expanded to 60 transliteration pairs |
| 2026-03-11 | source_quality | 2.1 → 2.9 | **TAINTED** | Primary registry timeouts → silent aggregator fallback | Timeout + circuit breaker + `tier_1_share` gate |
| 2026-03-14 | hallucination (contradicted) | 0.002 → 0.019 | FAIL | Judge prompt drift after rubric v3 edit | Rubric v3.1 + judge recalibration |
| 2026-03-18 | risk_calibration (integrity) | ECE 0.06 → 0.14 | FAIL | Framework v2 reweighting not reflected in judge rubric | Judge rubric v2.1 + 40 analyst-labelled cases |
| 2026-03-21 | timeline (ordering) | 0.96 → 0.79 | TAINTED | Undated events sorted by ingestion time | Sort policy + `undated_rate` gate |

## The interesting ones

**2026-03-11** passed every boolean threshold in the suite at the time.
Groundedness was 0.93. Hallucination was 0.004. Entity resolution was 0.96.
Only source-quality moved, and only because someone had added `tier_1_share`
three weeks earlier on a hunch. That hunch is ADR-003.

**2026-03-07** moved the global entity-resolution F1 from 0.961 to 0.958 —
well inside any reasonable drift tolerance. Every dashboard was green. The
MENA cohort was failing one in eight. It was caught because a golden case
tagged `transliteration` failed and someone looked at the tag distribution.
That's luck, not process. ADR-004 is the fix.

## Judge–human calibration over time

| Month | Judge–human agreement | Judge abstention | Human review sample |
|---|---|---|---|
| 2026-01 | 0.78 | 4% | 120 claims |
| 2026-02 | 0.84 | 7% | 140 claims |
| 2026-03 | 0.89 | 11% | 160 claims |

Agreement is up and abstention is up. That's the right direction. A judge
with 100% agreement and 0% abstention has stopped thinking.

## Risk-calibration against analysts over time

| Month | Overall agreement | Overall MAE | Overall ECE | Worst category |
|---|---|---|---|---|
| 2026-01 | 0.68 | 22.4 | 0.14 | integrity (bias +14) |
| 2026-02 | 0.74 | 19.1 | 0.11 | cybersecurity (bias +9) |
| 2026-03 | 0.81 | 15.8 | 0.08 | none above gate |