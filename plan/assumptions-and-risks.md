# Assumptions And Risks

## Current Assumptions

- the existing local folder already satisfies the “make a dir called `ClauseAIProd`” requirement
- implementation should stop after planning in this turn
- California law plus U.S. Code are the initial law corpora, with schema room for later expansion
- OpenStates remains the primary bill-history source
- object storage can remain local-first for development and become S3-compatible for production

## Main Risks

### 1. Reference corpus size

Risk:

- full OpenStates plus California plus U.S. Code can become heavy fast

Mitigation:

- flatten to app-facing tables only
- avoid carrying raw upstream schemas into production

### 2. Prompt drift

Risk:

- report quality can regress silently across stages

Mitigation:

- prompt versioning
- eval harness
- golden fixtures

### 3. Editor complexity

Risk:

- the collaborative drafting surface can become unstable if suggestions, manual edits, and version history are not modeled cleanly

Mitigation:

- explicit suggestion and version tables
- never rely on one mutable workflow blob

### 4. Desktop divergence

Risk:

- Electron-specific behavior can fork from web behavior

Mitigation:

- one shared React app
- Electron only owns shell and native bridges

### 5. Legal retrieval precision

Risk:

- conflict analysis may over-flag vague risks if retrieval and ranking are loose

Mitigation:

- canonical legal index
- exact citation expansion
- deterministic backstops for obvious cases

## Approval Points To Confirm Before Build Starts

- keep the exact hyphenated DB names, quoted in SQL
- replace Supabase auth entirely with first-party email/password auth
- keep local/S3 storage abstraction rather than storing large files directly in Postgres
- treat the current repo references as source material only, not code to vendor wholesale
