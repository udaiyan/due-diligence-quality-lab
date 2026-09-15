# ADR-004: Segment-aware evals, because aggregate metrics hide cohort regressions

**Status:** Accepted
**Date:** 2026-03-21
**Supersedes part of:** ADR-001

## Context

The golden set was originally a flat list of cases. Metrics rolled up to a
single number per signal. This was simpler and it was wrong.

On 2026-03-07, an unrelated resolver change dropped Arabic→Latin
transliteration recall from 0.97 to 0.88 across the MENA cohort. The global
entity-resolution F1 moved from 0.961 to 0.958. Every dashboard was green.

The regression was caught — but only because a golden case tagged
`transliteration` failed and someone looked at the tag distribution rather
than the mean. That's luck, not process.

## Decision

Every `EvalCase` carries a `segment`. Every metric rolls up globally *and*
per segment. Every threshold has both a global floor and a per-segment floor,
and both must pass.

Frameworks are segment-conditional. A university donor check and a corporate
supplier check have different risk categories, different weights, and
different bands.

## Consequences

**Good.** The MENA regression would have failed T2 in this scheme, on the
`entity_resolution.transliteration_f1` metric for the `law_firm` and
`professional_services` segments, without anyone having to notice a tag.

**Good.** Risk scoring is now honest about the fact that "risk" means
different things to different customers.

**Cost.** The golden set is harder to grow. A new case needs a segment, a
framework, and a band per category. The band in particular requires an
analyst to say what "acceptable" looks like, which is a conversation.

**Cost.** Reports are longer. A run produces one summary per segment plus a
global summary.

**Cost.** Small cohorts are noisy. A segment with 8 golden cases will produce
unstable per-segment numbers. We accept this as a coverage problem: the fix
is more golden cases for that segment, not a looser threshold.

## What we considered and rejected

**Weighting segments by customer count.** Every customer's failure is a
failure. A bank regression that affects 3 customers is still a regression.

**Inferring segment from the query.** Would introduce a classification
problem with its own calibration needs. The case author knows the segment.

**A universal risk framework with segment-specific weights.** Considered and
rejected. The *categories* differ between segments, not just the weights.