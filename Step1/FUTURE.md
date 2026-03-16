# Future Work

This document describes what still has to happen for Step1 to become both very accurate and very fast.

Short version:

- The current system is useful.
- It is not exhaustive.
- It cannot honestly claim `99.99%` accuracy yet.
- Reaching that standard requires a narrower definition of "similar", a labeled evaluation set, stronger offline indexing, and a more disciplined reranking stack.

## First Constraint

`99.99% accuracy` is not a meaningful claim until these are defined:

1. What counts as "similar"?
   - direct statutory analog
   - same program area
   - same legal mechanism
   - same affected population
   - same enforcement structure
   - same outcome class
2. What is the evaluation unit?
   - top 5 results
   - top 10 results
   - recall of all materially relevant bills
   - enacted bills only
   - same-state only or cross-state too
3. What counts as "missing"?
   - a bill absent from the top 10
   - a bill absent from the top 50
   - a bill absent entirely from the candidate pool

Without that, "99.99%" is marketing, not engineering.

## Current State

Step1 currently does:

1. file extraction
2. bill profiling with Codex OAuth `gpt-5.4`
3. state-aware PostgreSQL lexical retrieval
4. local sentence-transformer semantic reranking
5. final Codex reranking on the top slice

This is the right base architecture, but the system still has gaps:

- candidate recall is not yet exhaustive
- semantic features are created only for the uploaded bill, not precomputed for the whole corpus
- the final LLM rerank window is still small
- result buckets are not separated into direct analogs vs adjacent related bills
- there is no formal evaluation harness or gold standard

## What Has To Be Built

## 1. Define Similarity Properly

Create explicit labels for bill relationships:

- `direct_analog`
- `same_policy_domain`
- `same_mechanism`
- `same_affected_entities`
- `same_program_or_act`
- `procedural_or_oversight_analog`
- `weak_related`
- `not_similar`

The app should eventually return grouped results instead of one flat list:

- direct analogs
- adjacent related bills
- enacted analogs
- failed/dead analogs
- same-state analogs
- cross-state analogs

This matters because many "misses" are really ranking-category mistakes.

## 2. Build a Gold Evaluation Set

This is the single most important missing piece.

Create a benchmark set of uploaded bills with human-reviewed targets:

- at least `500` hard evaluation bills to start
- at least `20-50` labeled candidate judgments per evaluation bill
- include hard negatives:
  - same words, wrong meaning
  - same topic, different mechanism
  - same act family, different operational goal
  - broad omnibus bills with incidental overlap

Track:

- recall@10
- recall@25
- recall@50
- precision@5
- precision@10
- MRR
- NDCG
- same-state recall
- cross-state recall
- enacted-only recall

If the system cannot measure those, it cannot be driven toward 99.99%.

## 3. Precompute Rich Semantic Data For Every Bill

Right now the uploaded bill gets a rich semantic profile, but the corpus mostly does not.

Build an offline indexing pipeline that precomputes for every bill:

- normalized title
- normalized summary
- dense summary text
- legal mechanism tags
- affected entities
- enforcement/oversight tags
- program/agency tags
- statute/code citations
- timeline/process tags
- outcome/status bucket
- direct bill-level embedding
- section/chunk embeddings

Recommended tables:

- `bill_index`
  - one row per bill
  - metadata, status, summary, tags, normalized fields
- `bill_semantics`
  - precomputed GPT-derived semantic fields
- `bill_chunks`
  - chunked bill text
- `bill_chunk_embeddings`
  - vector rows for each chunk
- `bill_links`
  - related bills, citations, source links, versions

Without this, retrieval keeps depending too much on on-the-fly query phrasing.

## 4. Use Multi-Lane Retrieval

One retrieval lane is not enough.

The production design should run all of these in parallel:

- lexical full-text retrieval
- title/subject retrieval
- dense bill embedding retrieval
- dense chunk retrieval
- statute-citation retrieval
- program/agency/entity retrieval
- graph retrieval
  - related bills
  - same act family
  - shared citations
  - shared committees/agencies

Then union and dedupe the results before reranking.

Why this matters:

- some bills match by wording
- some match by program
- some match by mechanism
- some match only through the same cited statutes or agencies

The current app only captures part of that.

## 5. Replace Generic Vector Search With Better Retrieval Infrastructure

The current local semantic rerank is acceptable for Step1 but not enough for near-exhaustive search.

Upgrade to:

- `pgvector` with HNSW indexes, or
- a dedicated ANN engine such as `Qdrant` or `FAISS`

Store:

- one embedding for the whole bill summary
- one embedding for title + summary
- multiple embeddings for chunks or sections
- optional embeddings for extracted semantic summaries

This allows:

- faster retrieval
- better recall for conceptually similar but textually different bills
- far less on-the-fly embedding work

## 6. Add a Stronger Reranking Layer

The current reranker is:

- local sentence-transformer score
- final Codex judge on a bounded top set

That should become:

1. first-pass retrieval
2. second-pass semantic rerank
3. third-pass high-precision rerank

Good third-pass options:

- cross-encoder reranker fine-tuned for legal/policy text
- GPT-5.4 / Codex judge prompt with calibrated rubric
- hybrid scoring that mixes:
  - semantic similarity
  - mechanism overlap
  - entity overlap
  - citation overlap
  - jurisdiction relevance
  - outcome relevance

The final judge should score categories separately, not just "overall similarity".

## 7. Penalize Broad Bills More Intelligently

Broad budget, trailer, omnibus, and catch-all developmental-services bills will keep polluting results unless they are modeled explicitly.

Build a `bill_scope` classifier:

- narrow targeted bill
- act-wide reform bill
- omnibus bill
- trailer bill
- budget bill

Then penalize broad bills unless the user explicitly wants broad analogs.

This is one of the main reasons noisy results appear high.

## 8. Separate Recall Mode From Precision Mode

Production search should support two internal modes:

- `recall mode`
  - gather every plausible candidate
  - used for backend search and analysis
- `precision mode`
  - return only the strongest direct analogs
  - used for the user-facing top results

The system should not use the same cutoffs for both.

Recommended defaults:

- recall pool: `500-2000`
- semantic rerank pool: `200-500`
- final LLM rerank pool: `50-100`
- UI display: `10-25`

Current Step1 is still too shallow for the hardest cases.

## 9. Cache Everything Expensive

For speed, cache:

- uploaded bill profiles
- uploaded bill embeddings
- recurring query expansions
- corpus semantic rows
- final candidate explanations

Use:

- Redis or Postgres cache table
- content-hash cache keys for uploaded bills

This matters because real users will re-run similar uploads and filters.

## 10. Move Long-Running Work Offline

A production version should not regenerate expensive corpus data during requests.

Run offline jobs for:

- bill normalization
- semantic profiling
- chunking
- embeddings
- graph links
- status derivation
- evaluation reports

Recommended structure:

- nightly or incremental indexing job
- background workers for newly ingested bills
- materialized search tables for the app tier

## 11. Add Better Legislative Features

To approach near-exhaustive similarity, search cannot depend only on raw text meaning.

Add features such as:

- cited code sections
- agency names
- committee names
- sponsor clusters
- funding/appropriation flags
- notice/appeal/hearing flags
- timeline/deadline flags
- foster youth / disability / housing / wildfire etc. domain tags
- legal action verbs:
  - require
  - prohibit
  - authorize
  - report
  - fund
  - waive
  - appeal
  - deny
  - disclose

These features make the difference between "same words" and "same mechanism".

## 12. Add Failure Analysis Tooling

Every search run should eventually log:

- missed known relevant bills
- why they were missed
  - not retrieved
  - retrieved but weak semantic score
  - retrieved but LLM demoted
  - over-penalized as broad
- latency by stage
- query phrases used

You need a repeatable failure review loop, not ad hoc debugging.

## 13. Build a Test Harness

Add automated tests for:

- extraction
- profile schema stability
- retrieval recall on known cases
- ranking order on labeled cases
- regression tests for previously missed bills

Especially important:

- AB 1099-style regression cases
- cross-state analog cases
- vague title but strong mechanism cases
- broad omnibus false-positive cases

## 14. Improve The UI Output

The UI should not only show a score.

It should show:

- why this bill matched
- which dimensions matched
- direct analog vs adjacent related
- enacted / failed / in progress
- same-state vs cross-state
- source links
- confidence level

This improves trust and makes it easier to debug user complaints.

## Practical Roadmap

### Phase 1: Recall

Goal: stop missing obviously relevant bills.

- build `bill_index`, `bill_semantics`, `bill_chunks`
- widen retrieval lanes
- precompute embeddings
- raise candidate recall pool
- add regression set for known misses

### Phase 2: Ranking Quality

Goal: stop returning broad but weak analogs high in the list.

- add bill-scope classifier
- add mechanism/entity/citation scoring
- add grouped result buckets
- improve final reranker rubric

### Phase 3: Speed

Goal: get strong results fast enough for interactive use.

- move embeddings and semantic features offline
- add ANN search
- add caching
- remove remaining expensive per-request joins

### Phase 4: Measurement

Goal: prove quality instead of guessing.

- build gold labels
- run benchmark jobs
- track recall/precision regressions in CI
- publish scorecards for each pipeline change

## What "99.99%" Would Actually Require

To get close to that standard in a defensible way, you would need:

- a scoped definition of similarity
- a very large human-labeled benchmark
- multiple retrieval lanes
- precomputed semantic and citation features for the full corpus
- strong reranking
- regression tests on every change
- continuous measurement

Even then, "never miss anything" is not realistic for an open-ended legislative corpus unless you narrow the problem definition heavily.

The right goal is:

- near-exhaustive recall for a clearly defined similarity class
- very high precision in the top results
- explicit confidence and grouping in the UI

That is a real engineering target.
