# Google Research Notes

## Why Gemini 2.5 Flash

Use `gemini-2.5-flash` for the agentic planner and reranker.

Reasoning:
- low-latency model suitable for repeated retrieval loops
- better cost profile than heavier reasoning models
- appropriate for query planning, rewrite generation, and result explanation

## Why gemini-embedding-001

Use `gemini-embedding-001` for bill and query embeddings.

Reasoning:
- official stable embedding model
- supports flexible embedding dimensions
- intended for retrieval tasks

## Scalable retrieval direction from Google docs

Google's current search stack guidance points toward:
- hybrid search: dense + sparse retrieval
- reranking after retrieval
- vector indexes for large corpora
- agentic planning on top of retrieval, not in place of retrieval

## How this maps into Clause

### Near-term local app design
- SQLite full-text search for fast local lexical retrieval
- optional Gemini embeddings stored per bill for semantic recall
- agentic search uses Gemini to:
  - classify intent
  - rewrite search queries
  - choose filters
  - rerank evidence-backed candidates

### Large-scale production direction
- move the corpus into a serviceable primary store
- keep lexical indexes for identifiers and citations
- add vector index infrastructure for dense retrieval
- merge and rerank the candidate pool
- log every search plan and evidence path for auditability

## Practical production guidance

- lexical retrieval remains mandatory for exact bill IDs and rare legal phrases
- embeddings improve policy-intent recall
- hybrid retrieval should happen before the agent loop
- the agent loop should decide how to search, not hallucinate what exists
- every result shown to the user should have explicit match reasons

