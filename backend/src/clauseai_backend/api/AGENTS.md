# API Layer Guide

## Responsibilities
- Authenticate requests
- Validate inputs
- Call services/workflows
- Return stable response shapes

## Avoid
- Embedding prompt text in route handlers
- Duplicating DB query logic that already belongs in services
- Mixing cross-stage workflow behavior into multiple endpoints

## Conventions
- Keep endpoints aligned to product surfaces: auth, projects, pipeline runs, workflow content, reference search, chat, editor/export.
- If a route depends on long-running stage execution, surface explicit run state and clear error summaries.
- Prefer explicit `404`/`409`/`400` behavior over silent fallbacks.
