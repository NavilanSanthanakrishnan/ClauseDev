# Backend Package Guide

## Package Layout
- `api/`: authenticated HTTP endpoints
- `core/`: config and framework setup
- `db/`: database sessions and base helpers
- `models/`: SQLAlchemy models
- `schemas/`: request/response shapes
- `services/`: model calls, analysis, chat, drafting, extraction, export logic
- `workflows/`: pipeline execution and orchestration

## Design Intent
- API layer should orchestrate, not own domain logic.
- Services should be composable and testable without HTTP.
- Workflows should own stage execution order and persisted run state.
- Keep model-facing code isolated so prompts, parsing, retries, and auth changes do not leak across the app.

## Persistence Expectations
- Pipeline runs, artifacts, suggestions, versions, and chat all need durable storage.
- Stages should be resumable from database state, not only from in-memory assumptions.
- Avoid adding transient-only workflow state unless there is a strong reason.
