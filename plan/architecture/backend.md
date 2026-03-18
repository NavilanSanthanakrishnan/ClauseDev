# Backend Plan

## Stack

- FastAPI
- SQLAlchemy 2.x
- Alembic
- Pydantic v2
- psycopg 3
- Postgres-backed worker loop
- structured logging
- Playwright tooling only where web fetches need rendering

## Why FastAPI Again

- already proven across the reference repos
- easy migration path for reusable service logic
- good fit for async file handling, typed APIs, and incremental job polling

## Module Layout

```text
backend/app/
├── api/
│   ├── auth.py
│   ├── projects.py
│   ├── bills_db.py
│   ├── laws_db.py
│   ├── pipeline.py
│   ├── editor.py
│   └── chat.py
├── core/
│   ├── config.py
│   ├── security.py
│   ├── db_user.py
│   ├── db_reference.py
│   └── storage.py
├── services/
│   ├── extraction/
│   ├── metadata/
│   ├── similarity/
│   ├── legal/
│   ├── stakeholder/
│   ├── editor/
│   └── prompts/
├── workflows/
│   ├── orchestrator.py
│   ├── stage_runner.py
│   └── state_store.py
└── schemas/
```

## Auth Endpoints

- `POST /auth/signup`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`

Implementation:

- Argon2id password verification
- signed JWT access token
- hashed refresh token persistence

## Core API Groups

### Project / draft APIs

- create project
- upload source document
- fetch current draft
- fetch draft versions
- restore draft version

### Reference search APIs

- bill search
- bill detail
- law search
- law detail

### Pipeline APIs

- start stage run
- poll run status
- fetch stage artifact
- rerun stage

### Editor APIs

- list suggestions
- fetch suggestion detail
- accept suggestion
- reject suggestion
- apply modified suggestion

### Chat APIs

- create thread
- send message
- retrieve thread history

## Workflow Engine

The backend should not treat the pipeline as one opaque request.

Plan:

- each stage is a named run
- each run has deterministic steps
- steps persist inputs/outputs/errors
- UI polls run state or opens a server-sent event stream
- failed stages are retryable without destroying earlier stages

## Service Reuse Mapping

From `ClauseAI-Navilan` and `ClauseAI-Shrey`:

- bill extraction helpers
- bill profiling logic
- similar-bills ranking pipeline

From `ClauseAI-Navilan Step4`:

- legal index lookup patterns
- conflict classification heuristics
- deterministic California drafting/process backstops

From `ClauseAI`:

- route organization
- staged tests
- editor/report UI flow concepts

## Prompt / Model Layer

Each stage will expose:

- structured input builder
- system prompt
- user prompt
- JSON schema for expected output
- post-processor / validator

This prevents free-form brittle parsing.

## Storage Adapter

Keep file storage behind an interface:

- `save_blob`
- `read_blob`
- `delete_blob`
- `signed_url`

Phase 1 implementations:

- local filesystem adapter
- S3-compatible adapter

## Observability

- request IDs
- pipeline run IDs
- per-step timing
- model call audit metadata
- storage operation logs
- export job logs

## Backend Definition Of Done

- all routes typed and documented
- both databases wired cleanly
- worker can resume interrupted runs
- each stage emits structured artifacts
- tests exist per stage and across the full workflow
