# Search Plan

## Product Requirement
Bill lookup must be highly accurate. The interface should support:
- a standard precise search path
- a guided or agentic search path

## Search Modes

### 1. Standard Search
Use when the user knows what they want.

Inputs:
- query
- jurisdiction
- session
- status
- topic
- outcome
- sort

Execution:
- exact identifier and citation matching
- inferred jurisdiction and topic filters from the query text
- lexical ranking through SQLite FTS
- concept and topic expansion before retrieval
- optional Gemini embedding boosts when vectors exist
- deterministic reranking with match reasons

### 2. Guided Search
Use when the user asks for intent-driven discovery, such as:
- similar bills
- conflicting bills
- bills with the same policy pattern across states

Execution:
- parse request into search intent
- derive filters and evidence targets
- run retrieval across multiple candidate strategies
- rerank on evidence density and core policy-term alignment
- return explanation for why each bill matched

## Current Local Data Shape
- local development store: SQLite
- current retrieval index: `bill_fts` FTS5 table plus structured indexes
- local import source: OpenStates Postgres runtime
- import modes:
  - `balanced`: a small number of recent bills per jurisdiction for broad coverage
  - `recent`: the latest bills overall when recency matters more than state coverage

## Current Gap
- live semantic retrieval is wired but inactive until Gemini API keys are added and vectors are generated
- current local corpus size controls recall more than the ranking code does

## Data Source Direction
- Federal: Congress API as a high-trust official source
- State: OpenStates as the initial broad coverage source
- Optional supplement: licensed commercial feeds only if recall gaps justify them

## Why hybrid search
- lexical search is required for bill numbers and exact citations
- semantic search improves recall for policy-intent phrasing
- reranking is required for production quality ordering
- agentic search should orchestrate retrieval, not replace retrieval

## Phase 1 database indexes
- B-tree on identifiers, jurisdictions, sessions
- GIN full-text indexes for title and summary
- `pg_trgm` indexes for fuzzy title matching
- vector index for embeddings

## Output requirements
- every result should expose evidence:
  - identifier
  - jurisdiction
  - status
  - summary
  - matched reasons
  - source links
