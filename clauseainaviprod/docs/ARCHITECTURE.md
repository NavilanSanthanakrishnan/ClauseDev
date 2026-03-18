# Architecture

## Goal
Build `Clause` as a desktop-first Electron app with a production-grade Bills search experience.

## Stack
- Electron for desktop packaging on macOS and Windows
- React + Vite + TypeScript for frontend
- FastAPI + SQLAlchemy for backend
- PostgreSQL as primary database
- `pg_trgm` + full text + vector search for retrieval

## Top-Level Boundaries
```text
Electron Shell
├── Frontend Renderer (React)
│   ├── Shared app shell
│   ├── Bills lookup page
│   ├── Standard search mode
│   └── Guided/agentic search mode
└── Backend API (FastAPI)
    ├── Bill search endpoints
    ├── Bill detail endpoints
    ├── Search orchestration
    └── Data ingest jobs
```

## Initial Screen Model
```text
AppShell
├── Sidebar
│   └── Bills
└── Bills Workspace
    ├── Search header
    ├── Search mode switcher
    ├── Filter rail
    ├── Result list
    └── Bill detail panel
```

## Backend Layers
```text
API
├── routes
├── schemas
├── services
├── repositories
└── data jobs
```

## Retrieval Strategy
1. Structured filters narrow the corpus.
2. Lexical ranking captures citations, identifiers, sponsor names, and exact policy terms.
3. Semantic retrieval expands near matches.
4. Reranking produces the final ordered list.
5. Agentic mode converts user intent into retrieval instructions and evidence-backed explanations.

## Initial Non-Goals
- Auth
- Editing workflow
- Multi-tab navigation
- Export pipeline

