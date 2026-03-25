# Backend Guide

## Stack
- FastAPI
- SQLAlchemy ORM
- Psycopg/Postgres
- `uv` for dependency and command execution
- Codex-backed model calls through local OAuth credentials

## Entry Points
- App server: `uv run clauseai-api`
- User DB bootstrap: `uv run clauseai-bootstrap-user-db`
- Main package root: `src/clauseai_backend/`

## Database Boundaries
- `clauseai-db-user`: all mutable application state
- `clauseai-db`: read-mostly legal/bill reference corpus

## Implementation Rules
- Keep route modules focused on validation, auth checks, and response shape.
- Put durable workflow behavior in services/workflows, not inline in endpoints.
- Add schema changes carefully: user DB schema must support persisted resume/retry semantics.
- Prefer deterministic fallbacks when a live model call fails.
- Keep export behavior, suggestion application, and draft versioning idempotent where possible.
- Preserve the staged workflow contract:
  extraction and metadata happen before analysis; analysis artifacts and suggestions happen before the live editor.
- Treat `codex app-server` as the runtime for the final drafting workspace. The older one-shot Codex client remains useful for report generation but is not the editor runtime.
- Similar-bills, legal, and stakeholder stages should persist guidance only. Do not let those stages produce preapproved bill text patches; Codex drafts the actual edits later in the editor loop.
- Persist live editor state in the user database so the UI can poll and resume from durable session/event records.
- Restrict Codex file edits in the final editor to the draft workspace files intended for that session.
- Reference-database reads must fail fast in interactive routes. Prefer returning empty results to hanging on large corpus scans.

## Validation
- Run `uv run pytest` for backend changes.
- Run `uv run ruff check` for Python linting.
- If touching model-backed flows, verify at least one real end-to-end happy path.
