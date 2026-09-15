# ADR-002: Golden datasets are content-hashed and versioned like code

**Status:** Accepted
**Date:** 2026-01-22

## Context

The golden set lived in a single `cases.jsonl` with no version control beyond
git. A change to the file changed every metric on the next run, and nothing
in a report told you whether the numbers were comparable to last week's.

We had two incidents where a "regression" turned out to be a golden-set edit.

## Decision

Golden data lives in `datasets/golden/<version>/`:
datasets/golden/v2/
├── manifest.json ← { version, created, hash, case_count, changelog, owners }
└── cases.jsonl


`manifest.json` carries a `sha256:<16 hex>` hash computed over the sorted,
stripped lines of `cases.jsonl`. `load_manifest` recomputes and refuses to
proceed if the hash doesn't match.

Every `CaseReport` embeds the dataset hash it ran against. Reports with
different hashes are not comparable, and the report says so.

## Consequences

**Good.** No more "was this a regression or a golden-set change?" Two reports
with the same hash are comparable. Two reports with different hashes aren't.

**Good.** The changelog makes golden-set evolution legible. "38 new UBO cases
after MENA expansion" is a fact you can read.

**Cost.** Editing a golden case requires updating the manifest. This is
intentional friction — it's a change you should think about.

**Cost.** Version directories accumulate. v1 is an empty scaffold, kept so
the history is visible.

## What we considered and rejected

**Git SHAs as version identifiers.** Too coarse — a git SHA changes for
unrelated reasons.

**Content-addressed storage (e.g. IPFS).** Overkill for a few hundred cases.

**No versioning, just a changelog.** The changelog tells you what changed;
the hash tells you whether *what you're looking at now* matches what the
report says it ran against. You need both.