# ClauseAINaviProd

## Product
- Desktop-first Electron application named `Clause`.
- Initial scope is a single left-nav tab: `Bills`.
- Primary screen is `Bill Lookup`.
- No login/auth in v1.

## UX Direction
- Replicate the provided dark editorial UI direction first.
- Persistent left navigation should be a shared shell, not recreated per page.
- Main Bills experience should support:
  - standard bill search
  - higher-precision guided or agentic search
  - results list
  - bill detail panel on the right

## Architecture Constraints
- Start from scratch in this folder only.
- Keep code separated into `frontend`, `backend`, `electron`, `assets`, and `database`.
- Keep environment files outside this folder when possible.
- Build for macOS and Windows packaging through Electron.
- Reuse the frontend stack pattern from ClauseDev where appropriate.
- Push progress through the nested `ClauseDev` git repo so GitHub updates stay visible there.

## Data/Search Direction
- Bill lookup must favor accuracy over novelty.
- Plan for hybrid retrieval:
  - structured filters
  - lexical search
  - semantic retrieval
  - reranking
- Agentic search should be a second mode, not the only mode.

## Build Sequence
1. Lock architecture and data sources.
2. Define schema and indexing strategy.
3. Build backend search contracts.
4. Build shell and Bills UI.
5. Integrate retrieval modes.
6. Add packaging, tests, and observability.

## Non-Goals For First Pass
- Auth
- Multi-tab workspace
- Draft editor
- Full legislative workflow beyond bill lookup
