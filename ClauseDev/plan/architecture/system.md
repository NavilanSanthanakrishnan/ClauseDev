# System Architecture

## Top-Level Shape

```text
ClauseAIProd/
├── backend/                 FastAPI app, workers, prompt engine, DB adapters
├── frontend/                React + Vite web client
├── electron/                Electron main/preload/build config
├── infra/                   migrations, local dev scripts, packaging helpers
├── tests/                   cross-surface integration and Playwright suites
├── prompts/                 versioned prompt templates and JSON schemas
└── plan/                    this planning package
```

## Runtime Architecture

```text
React / Electron UI
        |
        v
     FastAPI
        |
        +--> "clauseai-db-user"
        |      auth, projects, drafts, workflow runs, suggestions, chat, history
        |
        +--> "clauseai-db"
               bills, laws, legal index, search docs, embeddings/profile inputs
```

## Service Split

### 1. API app

- session auth
- project and draft CRUD
- workflow run orchestration
- bill/law search APIs
- report and suggestion APIs
- editor and version-history APIs

### 2. Worker process

- extraction jobs
- metadata generation jobs
- similar-bill retrieval jobs
- bill analysis jobs
- conflict analysis jobs
- stakeholder analysis jobs
- prompt eval and background maintenance jobs

### 3. Ingestion jobs

- OpenStates flattening into bill search corpus
- California official code import
- U.S. Code import
- legal index build and refresh

## Major Architectural Decisions

### Two physical Postgres databases

Reason:

- reference data and user data have different scale, backup, retention, and migration patterns
- user DB must support transactional app flows without being coupled to huge ingestion rebuilds
- reference DB can be rebuilt or reindexed independently

### Postgres-backed job orchestration

Reason:

- durable state without adding Redis or a separate workflow system on day one
- resumable multi-stage jobs using row locks and explicit step state
- fewer moving pieces for local dev, Electron, and deployment

Mechanism:

- worker polls `workflow.pipeline_runs` and `workflow.pipeline_steps` in `"clauseai-db-user"`
- claims work using `FOR UPDATE SKIP LOCKED`
- stores every stage artifact and status transition

### Replace Supabase auth with first-party auth

Reason:

- user explicitly wants simple email + password with no verification
- avoids extra platform coupling
- keeps auth behavior identical across web and desktop

### Keep storage pluggable

Initial target:

- metadata in `"clauseai-db-user"`
- file blobs via a storage adapter

Phase 1 default:

- local disk for dev
- S3-compatible adapter for production

## Suggested Repo Scaffold

```text
backend/
├── app/
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── services/
│   ├── workflows/
│   ├── prompts/
│   └── schemas/
├── workers/
├── migrations/
└── scripts/

frontend/
├── src/
│   ├── app/
│   ├── pages/
│   ├── features/
│   ├── components/
│   ├── lib/
│   ├── hooks/
│   └── styles/

electron/
├── main/
├── preload/
└── build/
```

## Product Modules

- Homepage and marketing shell
- Email/password auth
- Your Bills dashboard
- Bills Database
- Laws Database
- Agentic Chatbot workspace
- Upload and extraction flow
- Metadata editor
- Similar bills browser and report
- Legal conflict report and fixes
- Stakeholder report and fixes
- Final collaborative drafting workspace
- Export and packaging
