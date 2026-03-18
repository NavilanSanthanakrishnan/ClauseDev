# ClauseAIProd

ClauseAI production app: FastAPI backend, React frontend, Electron wrapper, database bootstrap scripts, and end-to-end drafting workflow.

## What this runs

- Backend API: FastAPI on `http://127.0.0.1:8000`
- Frontend web app: Vite on `http://127.0.0.1:5173`
- Final drafting editor runtime: local `codex app-server`
- Databases:
  - `clauseai-db-user` for app state
  - `clauseai-db` plus source-specific reference databases for legal/reference data

## Prerequisites

- Python with `uv`
- Node.js and npm
- PostgreSQL with local databases available
- Codex CLI installed if you want the live final editor workflow

## AI backend options

The app supports two model backends at the same time:

1. OpenAI-compatible `/chat/completions`
   - Configured in the app at `/settings`
   - Saved in `backend/data/openai_settings.json`
   - Tried first when `base_url`, `api_key`, and `model` are all set
2. Codex OAuth fallback
   - Uses local credentials from `~/.codex/auth.json`
   - Used automatically when no OpenAI-compatible endpoint is configured

This means you can run the product either with:

- Codex only
- An OpenAI-compatible endpoint only
- Both configured, with OpenAI-compatible first and Codex as fallback

## Environment

The backend reads `.env` or `.env.local` with `CLAUSEAI_` prefixes.

Useful defaults already exist in code, including:

- `CLAUSEAI_USER_DATABASE_URL=postgresql+psycopg:///clauseai-db-user`
- `CLAUSEAI_REFERENCE_DATABASE_URL=postgresql+psycopg:///clauseai-db`
- `CLAUSEAI_OPENSTATES_DATABASE_URL=postgresql+psycopg:///openstates`
- `CLAUSEAI_CALIFORNIA_CODE_DATABASE_URL=postgresql+psycopg:///california_code`
- `CLAUSEAI_LEGAL_INDEX_DATABASE_URL=postgresql+psycopg:///clause_legal_index`
- `CLAUSEAI_USCODE_DATABASE_URL=postgresql+psycopg:///uscode_local`
- `CLAUSEAI_JWT_SECRET=change-me-in-env-change-me-in-env`

If you need a different frontend origin, update `CLAUSEAI_CORS_ORIGINS`.

## How To Run

### 1. Install dependencies

```bash
cd backend && uv sync
```

```bash
npm --prefix frontend install
```

### 2. Start the backend

```bash
cd backend && uv run clauseai-api
```

The backend boot process automatically ensures the user database schema exists.

### 3. Start the frontend

```bash
npm --prefix frontend run dev
```

Open `http://127.0.0.1:5173`.

## Running With Codex OAuth

Use this when you want the default local ClauseAI setup, including the final live drafting workspace.

1. Log into Codex locally:

```bash
codex login
```

2. Make sure `~/.codex/auth.json` exists after login.
3. Start the backend and frontend.
4. For the final editor flow, ensure `codex app-server` is available on your machine. The backend manages the runtime connection and expects the app-server on `127.0.0.1:8766` by default.
5. Leave `/settings` empty if you want pure Codex fallback behavior.

## Running With An OpenAI-Compatible URL

Use this when you want ClauseAI analysis and chat calls to go through any service that exposes `/chat/completions`.

Examples:

- OpenAI: `https://api.openai.com/v1`
- Ollama: `http://localhost:11434/v1`
- llama.cpp server: `http://localhost:8001/v1`
- LM Studio or compatible proxy: its `/v1` base URL

Steps:

1. Start the backend and frontend.
2. Sign in to the app.
3. Open `/settings` in the sidebar.
4. Save:
   - `Base URL`
   - `API key`
   - `Model name`
5. The backend will then call `POST {base_url}/chat/completions`.

Notes:

- The backend stores these settings in `backend/data/openai_settings.json`.
- If all three values are present, the OpenAI-compatible backend is marked active.
- Clearing the settings reverts model calls back to Codex OAuth automatically.
- The final drafting workspace still relies on local Codex app-server even when report-style model calls use the OpenAI-compatible endpoint.

## Useful Commands

- Backend dev server: `cd backend && uv run clauseai-api`
- Backend tests: `cd backend && uv run pytest`
- Backend lint: `cd backend && uv run ruff check`
- Frontend dev: `npm --prefix frontend run dev`
- Frontend checks: `npm --prefix frontend run typecheck`
- Frontend lint: `npm --prefix frontend run lint`
- Frontend build: `npm --prefix frontend run build`
- E2E tests: `npx playwright test`

## Recent UI/runtime changes

- Diff output now renders with a dedicated diff viewer instead of a plain text block.
- Markdown output now renders headings, emphasis, code, lists, rules, and fenced blocks without adding new npm dependencies.
- Page/card spacing has been tightened globally through CSS only.
- A new `/settings` page and `/api/settings/openai` API manage OpenAI-compatible endpoint configuration.
