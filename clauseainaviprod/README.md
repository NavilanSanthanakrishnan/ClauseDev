# Clause

Production-oriented Electron desktop app for legislative bill and law retrieval.

## Current scope
- Desktop shell for macOS and Windows
- Shared dark editorial app shell
- Bills lookup workspace
- Laws lookup workspace
- Standard retrieval mode
- Gemini-backed agentic retrieval mode

## Structure
- `frontend/` React + Vite renderer
- `backend/` FastAPI API
- `electron/` desktop shell
- `database/` local SQLite assets for bills and embeddings
- `docs/` architecture, search, and environment notes
- `scripts/` corpus import, vector build, and GitHub checkpoint tooling

## What is live now
- Bills database bootstrapped into local SQLite
- Bill search with exact match, FTS, inferred filters, optional embeddings, and agentic rerank
- Laws search over California Code and U.S. Code through external PostgreSQL corpora
- Full bill detail and law detail panels
- macOS packaging path verified with `electron-builder --dir`

## Runtime configuration
Environment stays outside the app folder in:

`/Users/navilan/Documents/ClauseAIProd/.env.clauseainaviprod`

See [docs/ENVIRONMENT.md](/Users/navilan/Documents/ClauseAIProd/clauseainaviprod/docs/ENVIRONMENT.md).

## Core commands
```bash
npm run dev:web
npm run dev:backend
npm run dev:desktop
npm run build:web
npx electron-builder --dir
```

## Data tooling
```bash
uv run python scripts/import_openstates_subset.py --limit 5
uv run python scripts/build_gemini_vectors.py
```

## Checkpointing
Use:

```bash
python scripts/checkpoint_to_clausedev.py --commit "message" --push
```

That mirrors this app into the GitHub-tracked `ClauseDev` repo.
