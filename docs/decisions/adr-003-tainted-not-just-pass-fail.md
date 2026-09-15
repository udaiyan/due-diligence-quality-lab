# ADR-003: `TAINTED` exists between `PASS` and `FAIL`

**Status:** Accepted
**Date:** 2026-03-14
**Context:** The harness originally returned a boolean per case.

## Problem

A boolean gate on a probabilistic system is wrong in both directions.

Too loose: a case passes because every metric cleared its threshold, even
though the *inputs* degraded — the primary registry timed out and the resolver
silently fell back to an aggregator. Groundedness barely moved (the aggregator
did contain the fact). Source quality moved from 2.1 to 2.9. The boolean said
green. It was lying.

Too tight: tightening thresholds until that case fails also fails dozens of
legitimate cases where an aggregator citation is entirely appropriate.

Neither setting is correct, because the question isn't "is this good enough?"
It's "is this the same as last time, and if not, why?"

## Decision

Three-valued verdicts:

- `PASS` — every metric in band, dataset hash matches baseline.
- `TAINTED` — metrics in band, but something upstream degraded: source tier
  slipped, judge abstention rose, dataset hash drifted, a layer was skipped.
- `FAIL` — a hard threshold was breached, or a layer raised.

`TAINTED` does not block merge. It *does* appear in the PR comment, it *does*
count against the weekly quality budget, and it *does* page if the taint rate
exceeds 5% over a rolling 7 days.

## Consequences

**Good.** The 2026-03-11 silent-fallback incident is now caught at T2 rather
than by a customer. The taint rate became a leading indicator: it rose for
three days before groundedness moved at all.

**Good.** It forces us to name what "degraded" means for each signal, which
turned out to be a useful design conversation in its own right.

**Cost.** Someone has to look at taints. We cap the daily taint review at 15
minutes and it's usually under 5. If the taint rate is sustained above 5%,
that's a signal the *thresholds* are wrong, not that the system is broken.

**Cost.** A three-valued verdict is harder to graph. The dashboard shows
taint rate and fail rate as separate series, never summed.