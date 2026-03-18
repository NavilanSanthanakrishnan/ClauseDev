# ClauseAIProd Plan

This directory is the planning package for the first implementation pass.

Current stage:

- GitHub repo is live at `shreyvish5678/ClauseAIProd`
- This repo is still planning-only
- No backend or frontend implementation has started yet
- The next step is your approval of these docs

Core decisions already locked:

- Primary reference database: PostgreSQL database named `"clauseai-db"`
- Primary app/user database: PostgreSQL database named `"clauseai-db-user"`
- Auth model: email + password only, no email verification
- Backend: FastAPI + SQLAlchemy + Alembic + Postgres-backed workflow jobs
- Frontend: React + Vite web app with Electron desktop wrapper
- Packaging targets: web, macOS `.dmg`, Windows `.exe`
- Frontend testing during build: Playwright MCP plus checked-in Playwright tests

Important note on the DB names:

- PostgreSQL allows hyphens in database names, but every SQL admin command must quote them.
- We will use `CREATE DATABASE "clauseai-db";` and `CREATE DATABASE "clauseai-db-user";`.

Documents in this plan:

- `source-review.md`: what was reviewed and what is reusable
- `architecture/system.md`: top-level system architecture and repo structure
- `data/reference-db.md`: exact plan for `"clauseai-db"`
- `data/user-db.md`: exact plan for `"clauseai-db-user"`
- `features/app-shell-and-auth.md`: homepage, auth, shell, and research surfaces
- `features/workflow-and-editor.md`: end-to-end drafting, analysis, and editing workflow
- `architecture/backend.md`: backend modules, APIs, jobs, and service boundaries
- `architecture/frontend-electron.md`: UI system, route map, Electron plan, packaging
- `quality/prompts-and-evals.md`: prompt system, structured outputs, and eval loop
- `quality/testing.md`: continuous testing strategy and Playwright MCP usage
- `delivery-phases.md`: implementation order, milestones, and commit cadence
- `assumptions-and-risks.md`: current assumptions, risks, and approval points

North star:

Build a serious legislative drafting workstation, not a toy chat app. Every analysis step must be durable, reviewable, attributable, and resumable. The editing workspace must preserve version history and show exactly why each suggested change exists.
