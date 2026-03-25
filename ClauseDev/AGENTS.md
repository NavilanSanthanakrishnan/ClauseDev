# ClauseAIProd Repository Guide

## Purpose
- This repo contains the production ClauseAI application: FastAPI backend, React web client, Electron desktop wrapper, infra SQL/scripts, tests, prompts, planning docs, screenshots, and read-only reference repos.
- The product center is a staged drafting workflow: upload -> extraction -> metadata -> similar bills -> legal -> stakeholders -> editor.
- The app uses two PostgreSQL databases:
  - `clauseai-db` for reference data materialized from OpenStates, `california_code`, `clause_legal_index`, and `uscode_local`
  - `clauseai-db-user` for app state, auth, projects, runs, drafts, suggestions, chat, and reports

## Repo Map
- `backend/`: FastAPI app, model runtime, workflow execution, persistence
- `frontend/`: Vite + React web UI
- `electron/`: desktop shell and preload bridge
- `infra/`: SQL bootstrap and shell scripts for databases
- `tests/`: Playwright and supporting test assets
- `prompts/`: source planning prompts and product-writing inputs
- `plan/`: build plan and analysis docs
- `repos/`: read-only inspiration/reference implementations
- `screenshots/`: UI reference images

## Core Commands
- Backend dev server: `cd backend && uv run clauseai-api`
- Backend tests: `cd backend && uv run pytest`
- Backend lint: `cd backend && uv run ruff check`
- Frontend dev: `npm --prefix frontend run dev`
- Frontend checks: `npm --prefix frontend run typecheck`, `npm --prefix frontend run lint`, `npm --prefix frontend run build`
- E2E tests: `npx playwright test`
- Desktop packaging: `npm run package:mac`, `npm run package:win`

## Engineering Rules
- Use `uv` for Python package and command execution.
- Keep API handlers thin. Put business logic in backend services/workflows.
- Keep React data-fetching in `frontend/src/lib/api.ts` and React Query hooks inside pages.
- Prefer fixing real user-flow issues over adding workaround UI.
- Preserve the explicit product workflow:
  `upload -> extraction -> editable metadata -> similar bills -> legal conflicts -> stakeholders -> final editor`.
- Treat analysis as report-first and edit-second. Similar-bills/legal/stakeholder stages generate artifacts and suggestions; the final editor is where agentic drafting happens.
- Upstream analysis stages must only save general drafting guidance. Concrete bill text changes are proposed only inside the final Draft Editor with approval gating.
- The final drafting workspace is powered by local Codex OAuth plus `codex app-server`, not by one-shot JSON suggestions alone.
- OpenAI-compatible `/chat/completions` support now coexists with Codex OAuth. If custom endpoint settings exist, try the OpenAI-compatible backend first; otherwise fall back to Codex OAuth. Do not remove either path unless the task explicitly requires it.
- Keep the final editor traceable: every AI draft mutation must remain reviewable, attributable, and versioned.
- Do not treat `repos/`, `plan/`, or `screenshots/` as runtime code unless the task explicitly asks for that.
- Preserve the two-database separation.
- Keep the repository-level README and security docs aligned with the supported runtime path. Public-facing docs must clearly distinguish `ClauseDev/` from the archival folders.
- When the reference database is still building, the UI should show honest status rather than pretending search is complete.
- Preserve the new `/settings` UX and `/api/settings/openai` REST flow. Stored endpoint settings live in `backend/data/openai_settings.json`.
- Treat `backend/data/` as local runtime state. Do not commit `openai_settings.json`, editor storage, or any other generated secret-bearing file.
- Keep markdown/report rendering structured. The app now uses a dedicated markdown renderer instead of raw pre-wrapped text for report content.
- Keep diff output rendered with the dedicated diff viewer and color-coded unified diff presentation rather than plain `<div>` text.
- UI density has been tightened globally; prefer extending the current spacing scale instead of reintroducing oversized card padding/gaps.

## Model / Prompt Runtime
- The backend is wired to local Codex OAuth credentials via `~/.codex/auth.json`.
- Default model is currently `gpt-5.4-mini` unless overridden by env.
- Prompt-backed analysis lives in backend services and `backend/data/prompts/`.
- OpenAI-compatible endpoint settings are user-configured at runtime through the authenticated settings API, not fixed in env by default.

## Read-Only vs Writable
- Writable implementation areas: `backend/`, `frontend/`, `electron/`, `infra/`, `tests/`
- Usually read-only context areas: `plan/`, `prompts/`, `repos/`, `screenshots/`
- Only edit read-only context areas if the task is specifically to improve docs/plans/prompts/reference notes.

## NON NEGOTIABLES
- Always use the Git CLI to commit and push code to GitHub periodically during implementation.
- Never leave work only local if it is in a meaningful state.
- Every meaningful change must include documentation updates.
- Every meaningful change to behavior, architecture, tooling, workflows, or conventions must also update the relevant `AGENTS.md` file(s).
- A task is not complete until:
  1. code is committed and pushed to GitHub,
  2. documentation is updated,
  3. relevant `AGENTS.md` files are updated.
