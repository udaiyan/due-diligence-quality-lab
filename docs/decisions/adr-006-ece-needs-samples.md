# ADR-006: ECE is only gated above a minimum sample size

**Status:** Accepted
**Date:** 2026-04-02

## Context

The entity-resolution calibration metric computes Expected Calibration Error
by binning predicted entities by confidence and comparing mean confidence to
empirical accuracy per bin. This is a population metric.

Running it against a case with one or two entities produces a number that
looks like a calibration signal but isn't. A single confident-correct entity
at confidence 0.88 produces ECE 0.12 — the same value it would produce for a
single confident-incorrect entity at the same confidence, because the
single-sample bin is either 0% or 100% accurate and the difference from 0.88
is arithmetic, not miscalibration.

The first run of the sample outputs surfaced this on a private-bank case
with one entity. The metric failed the case for a reason that had nothing to
do with the resolver's behaviour.

## Decision

`MIN_SAMPLES_FOR_ECE = 5`. Below that, the ECE value is still computed and
reported in `CaseReport.metrics` (so a reviewer can see it), but the failure
gate does not fire on it.

## Consequences

**Good.** Single-entity and small-cohort cases no longer fail on a metric
that can't be interpreted for them.

**Good.** The number is preserved, so a dashboard tracking ECE over time still
has data.

**Cost.** A genuinely mis-calibrated resolver on a small golden cohort will
not trip the ECE gate. Coverage is the fix — a segment with 3 golden cases
should grow to 30, not lower the sample threshold.

**Cost.** The threshold is a magic number. Five is the point at which 10 bins
average 0.5 entities per bin; below that, most bins are empty and the
weighted average collapses to one or two samples. It is empirical, not
principled, and should be revisited if the entity count per case changes
significantly.