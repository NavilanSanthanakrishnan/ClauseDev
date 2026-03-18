# ClauseAINaviProd Rules

## Scope
- Build only inside this folder unless the user explicitly asks otherwise.
- Keep the project easy to read: `frontend`, `backend`, `electron`, `assets`, `database`, `docs`, `scripts`.

## Git Discipline
- After any meaningful completed unit of work, check whether it should be committed.
- Do not treat this folder's local git state as the source of truth for pushes.
- Commit and push meaningful checkpoints through the nested `ClauseDev` GitHub repo.
- Before any commit, mirror the relevant `clauseainaviprod` changes into the `ClauseDev` git working tree.
- If the `ClauseDev` repo is not in a safe state for a focused commit, say so immediately.
- Keep commits focused and descriptive.

## Product Direction
- Desktop-first Electron app named `Clause`.
- First surface is `Bills` only.
- Primary experience is `Bill Lookup`.
- No auth in v1.

## UI Direction
- Persistent shared left nav shell.
- Dark editorial interface based on the provided references.
- Bills page should include:
  - standard search
  - guided or agentic search
  - filter controls
  - results list
  - right-side detail panel

## Search Direction
- Prioritize accuracy over novelty.
- Default to hybrid retrieval:
  - structured filters
  - lexical search
  - semantic search
  - reranking
- Keep agentic search as a separate mode layered on top of retrieval, not a replacement for it.
