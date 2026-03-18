# Architecture

## Goal
Build `Clause` as a desktop-first legislative drafting system where retrieval and drafting happen in one workflow.

## Stack
- Electron for macOS and Windows packaging
- React + Vite + TypeScript frontend
- FastAPI backend
- SQLite for local bills, search indexes, app state, projects, and sessions
- PostgreSQL corpora for California Code and U.S. Code
- Gemini for planning, reranking, embeddings, and workspace assistance

## Product Topology
```text
Electron Shell
├── Auth gate
├── Shared app shell
│   ├── Bills home
│   ├── Bill Lookup
│   ├── Law Lookup
│   └── Workspace
└── Backend API
    ├── Auth and session endpoints
    ├── Bill retrieval endpoints
    ├── Law retrieval endpoints
    ├── Project workspace endpoints
    └── Agent orchestration services
```

## Workspace Model
```text
Workspace
├── Bill brief
├── Draft text editor
├── Agent conversation
└── Intelligence rail
    ├── drafting focus
    ├── similar bills
    ├── conflicting laws
    └── stakeholders
```

## Backend Layers
```text
API
├── schemas
├── services
│   ├── standard_search
│   ├── agentic_search
│   ├── law_search
│   ├── agentic_law_search
│   ├── auth_service
│   └── project_workspace
└── repositories
    ├── bills
    ├── laws
    └── app_state
```

## Storage Boundaries
```text
SQLite
├── bills
├── bill_fts
├── bill_vectors
├── users
├── user_sessions
├── projects
├── project_insights
└── project_messages

PostgreSQL corpora
├── california_code.public.official_law_sections
└── uscode_local.public.usc_nodes
```

## Retrieval Strategy
1. Run structured filters first.
2. Use lexical retrieval for identifiers, citations, and exact policy terms.
3. Add semantic boosts where embeddings exist.
4. In agentic mode, let Gemini rewrite, broaden, and rerank the candidate pool.
5. In the workspace, reuse those retrieval tools instead of inventing a separate reasoning path.

## Product Rules
- Auth should be enforced from the backend and reflected by the frontend.
- The UI should keep navigation and meaning stable; the left rail is shared and persistent.
- The workspace is the primary moat because it converts retrieved evidence into draft output.

## Next Scale Direction
- Add more state law corpora behind the same legal retrieval interface.
- Move from local-only app state to a service-backed collaborative model when needed.
- Add richer citations and traceable evidence bundles to every agent response.
