# ClauseAI

ClauseAI is a staged legislative drafting workstation for bill intake, metadata generation, reference retrieval, legal conflict review, stakeholder analysis, and final drafting assistance.

This directory contains the actively supported application in the repository. If you cloned the top-level repo to understand what is current, this is the folder to run.

## Product Summary

ClauseAI is designed around a reviewable workflow instead of a single prompt box:

`upload -> extraction -> metadata -> similar bills -> legal -> stakeholders -> editor`

The intent is to keep upstream stages report-first and traceable:

- upload and extraction normalize source documents,
- metadata turns raw bill text into a structured legislative summary,
- similar-bills and legal stages produce research artifacts and guidance,
- stakeholder analysis surfaces likely support/opposition,
- the final editor is where approved drafting changes are generated and reviewed.

## Runtime Architecture

### Frontend

- React 19
- Vite
- React Router 7
- TanStack Query

Main routes:

- `/`
  marketing/home shell
- `/signup`, `/login`
  auth entry points
- `/bills`
  drafting home and project launch point
- `/bills/database`, `/laws/database`
  direct bill and law retrieval surfaces
- `/chat`
  corpus-backed research chat
- `/settings`
  OpenAI-compatible endpoint configuration
- `/projects/:projectId/*`
  staged drafting workflow pages and the final editor

### Backend

- FastAPI
- SQLAlchemy ORM
- Psycopg / PostgreSQL
- Pydantic Settings
- Uvicorn

Primary API surfaces:

- `/health`
  process health
- `/auth/*`
  signup, login, current-user, token flows
- `/api/projects/*`
  project CRUD, source document upload, metadata, artifacts, suggestions, drafts
- `/api/pipeline/*`
  stage execution and workflow orchestration
- `/api/reference/*`
  bill/law search and detail endpoints
- `/api/chat/*`
  research chat with corpus context
- `/api/settings/openai`
  authenticated runtime model configuration
- `/api/editor/*`
  final drafting runtime and event stream state

### Persistence Model

The current app separates mutable product state from large legal-reference corpora:

- `clauseai-db-user`
  required; stores auth, projects, workflow runs, artifacts, suggestions, chat, and editor session state
- `openstates`
  bill corpus for search and similar-bill analysis
- `california_code`
  California statutory corpus
- `clause_legal_index`
  unified legal-index corpus
- `uscode_local`
  federal U.S. Code corpus
- `clauseai-db`
  local materialization workspace used by `infra/sql/reference_db.sql`

Important implementation detail: the backend currently queries `openstates`, `california_code`, `clause_legal_index`, and `uscode_local` directly. `CLAUSEAI_REFERENCE_DATABASE_URL` is retained for infra/bootstrap workflows and should not be mistaken for the main runtime query target.

### Model Backends

ClauseAI supports two model paths:

1. OpenAI-compatible `/chat/completions`
   - configured from the authenticated `/settings` page
   - stored locally in `backend/data/openai_settings.json`
   - tried first when `base_url`, `api_key`, and `model` are all configured
2. Codex OAuth fallback
   - reads local credentials from `~/.codex/auth.json`
   - used automatically when no OpenAI-compatible endpoint is enabled

The final editor also expects a local `codex app-server` runtime for live drafting sessions.

## Repository Map

- `backend/`
  FastAPI app, database models, services, workflow orchestration, tests
- `frontend/`
  React UI
- `electron/`
  desktop shell and preload bridge
- `infra/`
  database creation/bootstrap scripts and reference SQL
- `tests/`
  Playwright smoke coverage
- `plan/`
  planning and architecture notes
- `prompts/`
  prompt source files for model-backed stages
- `repos/`
  read-only reference material and older mirrored implementations
- `screenshots/`
  UI evidence and visual references

## Local Prerequisites

- Node.js and npm
- Python 3.14+
- `uv`
- PostgreSQL available via local socket or local default `psql` config
- Optional:
  - `codex login` for Codex-backed flows
  - `codex app-server` for the final drafting editor

## Quick Start

### 1. Install dependencies

From this directory:

```bash
npm install
npm --prefix frontend install
(cd backend && uv sync)
```

### 2. Create and bootstrap the local databases

```bash
./infra/scripts/create_databases.sh
./infra/scripts/bootstrap_user_db.sh
```

`create_databases.sh` creates empty databases for all default DSN names. That is enough to boot the app and run smoke tests, but not enough to return real legal-search results until the external corpora are imported.

### 3. Create local env files

```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Recommended minimum values are already included in the examples. Replace `CLAUSEAI_JWT_SECRET` with a long random value before using anything beyond a throwaway local environment.

### 4. Start the backend

```bash
cd backend && uv run clauseai-api
```

The backend boot sequence automatically ensures the user-database schema exists.

### 5. Start the frontend

```bash
npm --prefix frontend run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173).

### 6. Optional: start the Electron shell

In another terminal from this directory:

```bash
npm run dev:desktop
```

## Minimal Versus Full-Fidelity Operation

### Minimal local mode

This mode is enough for:

- signup/login,
- project creation,
- source upload,
- metadata generation,
- page-by-page workflow navigation,
- backend and Playwright smoke tests.

In this mode:

- legal/reference databases may be empty,
- model credentials may be absent,
- similar-bills, legal, and chat flows fall back to empty or heuristic outputs instead of hard-failing.

### Full research mode

Use this mode if you want realistic retrieval and richer model output.

Required additional inputs:

- a local `openstates` PostgreSQL database populated with OpenStates-compatible bill tables,
- a local `california_code` database,
- a local `uscode_local` database,
- a local `clause_legal_index` database,
- either:
  - Codex OAuth credentials from `codex login`, or
  - an OpenAI-compatible endpoint configured in the app.

## How To Obtain The Reference Databases

The full corpora are not committed to this repository.

### `openstates`

Expected use:

- bill lookup
- similar-bill candidate retrieval
- corpus-backed research chat

Expected tables include:

- `opencivicdata_bill`
- `opencivicdata_billabstract`
- `opencivicdata_billaction`
- `opencivicdata_billversion`
- `opencivicdata_billsource`
- `opencivicdata_legislativesession`
- `opencivicdata_jurisdiction`

You can restore this from your own OpenStates PostgreSQL dump or adapt the older bootstrap work preserved in the historical folders.

### `california_code`

Expected use:

- California law lookup
- legal conflict stage

Historical ingest utilities live under `../OldClauseDev/Step2`.

### `uscode_local`

Expected use:

- federal law lookup
- legal conflict stage

Historical build/import utilities live under `../OldClauseDev/Step2/uscode`.

Example historical flow:

```bash
cd ../OldClauseDev/Step2
python3 uscode/scripts/build_uscode_db.py
python3 uscode/scripts/import_uscode_to_postgres.py --recreate
```

### `clause_legal_index`

Expected use:

- canonical law-search corpus
- broader legal-context retrieval

Historical build/index helpers live under `../OldClauseDev/Step4`.

Example historical flow:

```bash
cd ../OldClauseDev/Step4
python3 scripts/build_legal_index.py
python3 scripts/build_legal_semantics.py
```

### Optional `clauseai-db` reference workspace

If you want the materialized reference workspace defined by the current infra SQL:

```bash
psql clauseai-db -f infra/sql/reference_db.sql
```

This script creates FDW-backed imports from the source corpora and materializes search-facing tables locally. It is useful for experiments and future consolidation, but it is not the current primary query path used by the backend.

## Environment Variables

The backend reads `.env` or `.env.local` with the `CLAUSEAI_` prefix.

Common settings:

- `CLAUSEAI_USER_DATABASE_URL`
- `CLAUSEAI_OPENSTATES_DATABASE_URL`
- `CLAUSEAI_CALIFORNIA_CODE_DATABASE_URL`
- `CLAUSEAI_LEGAL_INDEX_DATABASE_URL`
- `CLAUSEAI_USCODE_DATABASE_URL`
- `CLAUSEAI_JWT_SECRET`
- `CLAUSEAI_CORS_ORIGINS`
- `CLAUSEAI_CODEX_APP_SERVER_HOST`
- `CLAUSEAI_CODEX_APP_SERVER_PORT`
- `CLAUSEAI_REFERENCE_QUERY_TIMEOUT_MS`

The frontend reads:

- `VITE_API_BASE_URL`

## Testing And Verification

### Backend

```bash
cd backend && uv run pytest
cd backend && uv run ruff check
```

### Frontend

```bash
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build
```

### End-to-end smoke coverage

```bash
npx playwright test
```

The current Playwright config starts:

- the backend on `127.0.0.1:8000`
- the preview frontend on `127.0.0.1:4173`

### Easy manual smoke test

1. Open `/signup`.
2. Create a local user.
3. Create a project from `/bills`.
4. Upload a `.txt`, `.docx`, or `.pdf` bill draft.
5. Trigger metadata generation.
6. Confirm the staged pages render and the draft editor opens.

If the reference corpora are empty, similar-bills and legal stages should stay operational but produce sparse results instead of crashing.

## Security Notes

- Runtime OpenAI-compatible settings are stored in `backend/data/openai_settings.json`.
- `backend/data/` is intentionally gitignored because it can contain local credentials and editor state.
- `.env` files are for local use only and should never be committed.
- Reference search queries use a short statement timeout by default so chat and analysis surfaces fail soft instead of hanging on oversized corpora.
- The repository was reviewed on March 24, 2026 for obvious secret leakage before publication; see [`../SECURITY.md`](../SECURITY.md).

## Packaging

Desktop packaging commands from this directory:

```bash
npm run package:mac
npm run package:win
```

These commands build the frontend and then package the Electron shell with `electron-builder`.
