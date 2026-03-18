# Architecture

## Goal
Build `Clause` as a desktop-first Electron app with production-grade bill and law retrieval.

## Stack
- Electron for desktop packaging on macOS and Windows
- React + Vite + TypeScript for frontend
- FastAPI + Python services for backend
- SQLite for local bill search state and embeddings
- PostgreSQL corpora for California Code and U.S. Code
- full text + embeddings + agentic reranking for retrieval

## Top-Level Boundaries
```text
Electron Shell
├── Frontend Renderer (React)
│   ├── Shared app shell
│   ├── Bills lookup workspace
│   ├── Laws lookup workspace
│   ├── Standard search mode
│   └── Agentic search mode
└── Backend API (FastAPI)
    ├── Bill search endpoints
    ├── Law search endpoints
    ├── Detail endpoints
    ├── Gemini planner and reranker
    └── Data ingest jobs
```

## Initial Screen Model
```text
AppShell
├── Sidebar
│   └── Retrieval workspace
└── Main Workspace
    ├── Bills lookup
    ├── Laws lookup
    ├── Search mode switcher
    ├── Filter rail
    ├── Result list
    └── Context-aware detail panel
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

## Data Sources
```text
Local SQLite
├── bills
├── bill_fts
└── bill_vectors

External PostgreSQL corpora
├── california_code.public.official_law_sections
└── uscode_local.public.usc_nodes
```

## Retrieval Strategy
1. Structured filters narrow the corpus.
2. Lexical ranking captures citations, identifiers, headings, and exact policy terms.
3. Bill search can add Gemini embedding boosts when vectors exist.
4. Agentic mode plans rewrites and reranks with Gemini.
5. Detail panels always expose the exact underlying text.

## Initial Non-Goals
- Auth
- Editing workflow
- Multi-tab navigation
- Export pipeline
