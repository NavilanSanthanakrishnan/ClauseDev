# Clause

Production-oriented Electron software for legislative drafting, bill retrieval, and law retrieval.

## What it is now
- Desktop shell for macOS and Windows
- React + Vite frontend
- FastAPI backend
- Local SQLite bill store
- External PostgreSQL law corpora for California Code and U.S. Code
- Gemini-backed agentic search and workspace assistance

## Current product surfaces
- `Bills`: drafting home with reusable bill workspaces
- `Bill Lookup`: normal and agentic bill retrieval
- `Law Lookup`: normal and agentic law retrieval
- `Workspace`: bill editor, intelligence rail, and agent loop

## Current capabilities
- Env-gated login flow with a dummy local account
- Hybrid bill search:
  - exact matching
  - inferred filters
  - SQLite FTS
  - optional Gemini embedding boosts
  - agentic planning and reranking
- Law search over California Code and U.S. Code
- Workspace refresh that loads:
  - similar bills
  - conflicting laws
  - stakeholders
  - drafting focus
- Workspace agent that works over the current draft context

## Structure
- `frontend/` renderer
- `backend/` API and retrieval services
- `electron/` desktop shell
- `database/` local bill data and schema
- `docs/` product, search, and environment notes
- `scripts/` import, vectors, smoke testing, and GitHub checkpointing

## Environment
Runtime config lives outside the project folder:

`/Users/navilan/Documents/ClauseAIProd/.env.clauseainaviprod`

See [ENVIRONMENT.md](/Users/navilan/Documents/ClauseAIProd/clauseainaviprod/docs/ENVIRONMENT.md).

## Core commands
```bash
npm run dev:web
npm run dev:backend
npm run dev:desktop
npm run build:web
npx electron-builder --dir
```

## Quality gates
```bash
cd backend && uv run pytest tests -q
npm --prefix frontend run build
python3 scripts/smoke_test.py
```

## Checkpointing into GitHub
```bash
python3 scripts/checkpoint_to_clausedev.py --commit "message" --push
```

That mirrors this app into the nested GitHub-tracked `ClauseDev` repo.
