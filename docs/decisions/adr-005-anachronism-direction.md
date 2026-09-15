# ADR-005: Anachronism is event-after-source, not event-before-source

**Status:** Accepted
**Date:** 2026-04-02

## Context

The timeline metric originally flagged an event as anachronistic if its date
**preceded** its cited source's publication date. The rationale was: "a source
cannot support an event that happened before the source existed."

That rationale is wrong. Sources document past events all the time. A 2022
news article legitimately reports a 1971 birth. A Companies House filing from
2021 legitimately records a 2015 directorship. The first run of the sample
outputs against the golden set flagged a law-firm case where a subject's DOB
was cited by a 2022 sanctions coverage article. That is retrospective
sourcing, not anachronism.

The actual anachronism is the inverse: an event dated **after** its source
was published. A 2015 source cannot know about a 2020 event.

## Decision

Anachronism is `event.date > source.published_at.date()`, not the reverse.

## Consequences

**Good.** Retrospective sourcing no longer fails the metric.

**Good.** The metric now catches what it was actually meant to catch: a
claim in a report that an event occurred before a source could have known
about it. That is a real fabrication signal.

**Cost.** The earlier smoke-test "fix" (changing a Companies House source's
`published_at` to match the event date) is no longer required. That fixture
change is retained because the 2015 date is more realistic, but it's no
longer load-bearing.

## What we considered and rejected

**Keeping the metric as-is and requiring every event to cite a
contemporaneous source.** Rejected: it would fail most real reports. Almost
no investigator finds a source published on the same day as an event.