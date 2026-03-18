# Source Review

## What Was Reviewed

- `prompts/prompt.md`
- `prompts/ui-prompt.md`
- `prompts/test-prompt.md`
- `prompts/workflow.md`
- `repos/ClauseAI`
- `repos/ClauseAI-Navilan`
- `repos/ClauseAI-Shrey`
- all screenshots in `screenshots/`
- current `21st.dev` agent docs entrypoint at `https://21st.dev/agents/llms.txt`
- current `fed10.ai` landing experience at `https://www.fed10.ai/`

## Main Findings

### ClauseAI

Useful to keep:

- the full FastAPI route split for pipeline stages
- the React/Electron app shape
- workflow persistence concepts
- prompt inventory layout
- existing backend integration test order

Not to keep as-is:

- Supabase magic-link auth
- Supabase-first persistence and storage assumptions
- overly broad workflow JSON blobs as the only persistence primitive

Decision:

- Reuse route and stage concepts.
- Replace auth and persistence with our own Postgres-backed model.

### ClauseAI-Navilan Step1

Useful to keep:

- hybrid similar-bill retrieval pattern
- OpenStates search bootstrap ideas
- staged lexical -> semantic -> LLM rerank pipeline
- bill profiling concept before retrieval

Not to keep as-is:

- dependence on raw OpenStates schema as app-facing surface
- local single-step app boundaries

Decision:

- Keep retrieval logic.
- Flatten only the needed OpenStates bill fields into our own reference tables.

### ClauseAI-Navilan Step2

Useful to keep:

- official California law ingest direction
- section-level normalization
- official code TOC plus section separation
- search views for law lookup

Not to keep as-is:

- entire staging footprint in the app-facing database
- duplicate crawl-era tables when official bulk data exists

Decision:

- Use official California bulk data as the primary California law source.
- Keep only the minimal normalized tables and search views needed by the product.

### ClauseAI-Navilan Step4

Useful to keep:

- canonical legal index concept
- legal retrieval tools: citation lookup, text search, semantic overlay, references, hierarchy neighbors
- conflict categorization and deterministic backstops
- benchmark mindset

Not to keep as-is:

- standalone app structure
- over-coupling between raw source tables and analysis layer

Decision:

- Rebuild the legal index as a clean module inside the new backend.
- Keep the canonical law document model.

### ClauseAI-Shrey

Useful to keep:

- alternate wording and workflow framing from Step1
- prompt direction for structural and comparative bill analysis

Decision:

- mine prompt and workflow patterns where they clarify the user-facing flow.

## Screenshot Requirements Extracted

The screenshots define hard product requirements:

- black-first, restrained, framed interface
- homepage with hero, login, and book-demo actions
- centered sign-in form
- persistent left sidebar
- separate pages for Your Bills, Bills Database, Laws Database, Agentic Chatbot
- upload -> extract -> metadata -> similar bills flow
- distinct report pages that surface fixes but do not silently apply them
- detailed fix pages with traceability
- drafting workspace with version history, backtracking, and agent loop
- responsive behavior that turns wide layouts into intentional stacked panels

## External Design Signals To Use

From `fed10.ai`:

- sharp editorial messaging
- dense intelligence panels without looking cluttered
- product demo surfaces that feel operational, not decorative
- “brief me, don’t bury me” information hierarchy

From `21st.dev`:

- high-quality modern component composition
- motion and layout discipline for polished interactions
- component-level finish, not generic template output

## Source-of-Truth Summary

Product truth order for the build:

1. user instructions in this repo
2. screenshots
3. `prompts/prompt.md`
4. reusable logic from `ClauseAI`, `ClauseAI-Navilan`, and `ClauseAI-Shrey`
5. current live design references from `fed10.ai` and `21st.dev`
