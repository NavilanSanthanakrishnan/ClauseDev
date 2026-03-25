# ClauseDev

ClauseDev is a repository of ClauseAI's legislative drafting and legal-research work. It contains the current application under `ClauseDev/`, an older production-oriented branch under `clauseainaviprod/`, and historical retrieval/indexing prototypes under `OldClauseDev/`.

If you are trying to run the current product, start in [`ClauseDev/README.md`](ClauseDev/README.md). The other top-level folders are useful for historical context and dataset bootstrapping, but they are not the main runtime path.

## What This Repository Is For

ClauseAI is an AI-assisted drafting workstation for bills, legislative analysis, and legal-reference search. The supported `ClauseDev/` application combines:

- a FastAPI backend for auth, projects, workflow orchestration, reference search, and editor sessions,
- a React + Vite frontend for the staged drafting flow,
- an Electron shell for desktop packaging,
- PostgreSQL-backed legal/reference corpora,
- local model integrations through Codex OAuth or an OpenAI-compatible `/chat/completions` endpoint.

The product workflow is explicit and stage-based:

`upload -> extraction -> metadata -> similar bills -> legal -> stakeholders -> editor`

## Repository Layout

- `ClauseDev/`
  The actively supported app. This is the path to use for local development, documentation, and testing.
- `clauseainaviprod/`
  An earlier production-oriented branch with a different architecture mix, SQLite persistence, and Gemini-specific tooling.
- `OldClauseDev/`
  Historical prototypes (`Step1`, `Step2`, `Step4`) used to build retrieval slices, corpus import scripts, and legal-index experiments.

Within `ClauseDev/`:

- `backend/`
  FastAPI application, SQLAlchemy models, auth, pipeline orchestration, and model-backed services.
- `frontend/`
  React 19 + Vite client for the drafting workflow and search surfaces.
- `electron/`
  Desktop wrapper and preload bridge.
- `infra/`
  Database creation and bootstrap scripts plus SQL for the reference workspace.
- `tests/`
  Playwright smoke tests.
- `plan/`, `prompts/`, `screenshots/`, `repos/`
  Planning material, prompt sources, UI references, and read-only reference repos.

## Tech Stack

Current supported app (`ClauseDev/`):

- Backend: Python 3.14, FastAPI, SQLAlchemy, Psycopg, Pydantic Settings, Uvicorn
- Frontend: React 19, React Router 7, TanStack Query, TypeScript, Vite
- Desktop: Electron
- Datastores:
  - `clauseai-db-user` for app/auth/project/workflow state
  - `openstates`, `california_code`, `clause_legal_index`, `uscode_local` for legal-reference search
  - `clauseai-db` as a local reference materialization workspace used by infra SQL
- AI/runtime integrations:
  - Codex OAuth via `~/.codex/auth.json`
  - OpenAI-compatible `/chat/completions` providers configured at runtime through the authenticated settings API
- Testing: `pytest`, `ruff`, Playwright, TypeScript build checks

## Supported Setup Paths

### Minimal smoke-test path

Use this if you want to verify the app boots, auth works, project creation works, and the workflow pages render:

1. Create the local app databases:

   ```bash
   cd ClauseDev
   ./infra/scripts/create_databases.sh
   ./infra/scripts/bootstrap_user_db.sh
   ```

2. Install dependencies:

   ```bash
   npm install
   npm --prefix frontend install
   (cd backend && uv sync)
   ```

3. Copy env templates:

   ```bash
   cp .env.example .env
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env
   ```

4. Start the backend and frontend:

   ```bash
   cd backend && uv run clauseai-api
   npm --prefix frontend run dev
   ```

This path works without importing the large reference corpora. Search-heavy and law-heavy flows will degrade to empty or heuristic results instead of crashing.

### Full research path

Use this if you want realistic bill/law retrieval and richer analysis outputs:

- restore or build local PostgreSQL databases named `openstates`, `california_code`, `clause_legal_index`, and `uscode_local`,
- optionally run `ClauseDev/infra/sql/reference_db.sql` against `clauseai-db` if you want the materialized reference workspace,
- configure either:
  - Codex locally with `codex login`, or
  - an OpenAI-compatible endpoint from the in-app `/settings` page.

Historical scripts for assembling the corpora live under `OldClauseDev/Step2`, `OldClauseDev/Step4`, and related helper folders. Those scripts are kept for reproducibility, but the supported runtime remains `ClauseDev/`.

## How To Get The Databases

The repo does not ship the full legal/reference corpora. To reproduce the full search stack you need local PostgreSQL databases with the default names below.

- `clauseai-db-user`
  Required. Created and bootstrapped by `ClauseDev/infra/scripts/bootstrap_user_db.sh`.
- `openstates`
  Optional for smoke tests, recommended for bill retrieval. Expected to contain OpenStates-compatible bill tables such as `opencivicdata_bill`, `opencivicdata_billabstract`, and related session/source tables.
- `california_code`
  Optional for smoke tests, recommended for California law lookup. Historical import helpers live under `OldClauseDev/Step2`.
- `uscode_local`
  Optional for smoke tests, recommended for federal law lookup. Build/import helpers live under `OldClauseDev/Step2/uscode/`.
- `clause_legal_index`
  Optional for smoke tests, recommended for the canonical unified law-search corpus. Historical build helpers live under `OldClauseDev/Step4`.
- `clauseai-db`
  Optional. Used by `ClauseDev/infra/sql/reference_db.sql` as a local materialization workspace.

Important: the current backend connects directly to `openstates`, `california_code`, `clause_legal_index`, and `uscode_local`. `CLAUSEAI_REFERENCE_DATABASE_URL` is still present for infra/bootstrap workflows, but it is not the primary runtime query path for the current backend.

## Security Status

As of March 24, 2026, this repository was reviewed for obvious secret leakage in the tracked working tree and for high-risk secret-bearing filenames in git history. No live API keys, OAuth tokens, or private-key files were found in the current tracked files.

The publishability hardening in this repo now assumes:

- local secrets stay in `.env` files or external secret stores,
- runtime-generated files under `ClauseDev/backend/data/` stay out of git,
- OpenAI-compatible endpoint settings are treated as local machine state,
- you should still enable GitHub secret scanning and rotate any credential that was ever shared outside your control.

See [`SECURITY.md`](SECURITY.md) for the current policy.

## Where To Start

- Product/runtime docs: [`ClauseDev/README.md`](ClauseDev/README.md)
- Historical prototype overview: [`OldClauseDev/README.md`](OldClauseDev/README.md)
- Earlier production branch: [`clauseainaviprod/README.md`](clauseainaviprod/README.md)
