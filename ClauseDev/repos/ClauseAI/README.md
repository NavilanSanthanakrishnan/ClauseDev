# ClauseAI

AI-powered legislative drafting and strategy platform.

## Overview

ClauseAI is a full-stack app (FastAPI + Electron/React) for end-to-end legislative bill analysis.

This repository now uses a Supabase-first architecture for:

- Authentication (magic-link auth)
- User/workflow persistence (Postgres)
- File storage (Supabase Storage)
- Business data source-of-truth (`backend/data` mirrored to Storage with read-through cache)

## Architecture

```text
ClauseAI/
├── backend/      # FastAPI API + analysis services
├── frontend/     # Electron + React desktop app
└── supabase/     # Supabase local config + SQL migrations
```

## Environment

Use repo-root env files:

- `/Users/shreyvishen/ClauseAI/.env.local`
- `/Users/shreyvishen/ClauseAI/.env.production`

Set `APP_ENV=local` (or `production`) before running backend.

## Quick Start (Local)

### 1. Supabase

```bash
cd /Users/shreyvishen/ClauseAI
supabase start
```

### 2. Backend

```bash
cd /Users/shreyvishen/ClauseAI/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
APP_ENV=local python main.py
```

API: `http://localhost:8000`

### 3. Frontend

```bash
cd /Users/shreyvishen/ClauseAI/frontend
npm install
npm run electron:dev
```

Web mode: `npm run dev` at `http://localhost:5173`

## Authentication Model

- Frontend requests Supabase one-time magic links.
- Backend requires `Authorization: Bearer <access_token>` for all protected endpoints.
- Backend verifies JWT and maps users to `app_users`.
- Approval gating is controlled by `SUPABASE_AUTH_APPROVAL_REQUIRED`.

## Key API Endpoints

```text
GET    /health
GET    /auth/status
GET    /api/user/me
PATCH  /api/user/me
GET    /api/workflow/current
PUT    /api/workflow/current
GET    /api/workflow/history
POST   /api/workflow/history/archive
POST   /api/workflow/history/restore
DELETE /api/workflow/history/{history_id}
POST   /api/bill_extraction/extract-text
GET    /api/bill_extraction/extract-text/status
GET    /api/bill_extraction/extract-text/result
POST   /api/title_description/generate-metadata
POST   /api/bill_similarity/find-similar
POST   /api/bill_inspect/inspect
POST   /api/similar_bills_loader/load-similar-bills
POST   /api/bill_analysis/analyze-bill
POST   /api/conflict_analysis/analyze-conflicts
POST   /api/stakeholder_analysis/analyze-stakeholders
```

## Data Migration Script

Upload business data to Supabase Storage (`business-data` bucket):

```bash
cd /Users/shreyvishen/ClauseAI/backend
python scripts/upload_business_data.py --resume
```

Use `--dry-run` to preview and `--state-file` to customize resumable state tracking.

## Docs

- Backend details: `/Users/shreyvishen/ClauseAI/backend/README.md`
- Backend tests: `/Users/shreyvishen/ClauseAI/backend/tests/README.md`
- Frontend details: `/Users/shreyvishen/ClauseAI/frontend/README.md`