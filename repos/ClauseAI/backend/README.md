# ClauseAI Backend

FastAPI backend for legislative bill analysis with Supabase-based auth/persistence/storage.

## What It Does

Pipeline stages:

1. Extract bill text from `pdf`, `docx`, or `txt`
2. Generate title, description, and summary
3. Retrieve balanced similar bills (passed + failed)
4. Inspect/clean bill text (`/api/bill_inspect/inspect`)
5. Load and categorize similar bill sentences
6. Generate bill analysis recommendations
7. Run legal conflict analysis
8. Run stakeholder analysis

## Supabase Integration

- **Auth**: bearer JWT from Supabase (`Authorization: Bearer <token>`)
- **User profile**: `public.app_users`
- **Workflow state**: `public.user_workflows`
- **Workflow history**: `public.workflow_history`
- **User file metadata**: `public.user_files`
- **Storage buckets**:
  - `user-files` (user-scoped uploads)
  - `business-data` (backend business corpus)

## Setup

```bash
cd /Users/shreyvishen/ClauseAI/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
APP_ENV=local python main.py
```

API base URL: `http://localhost:8000`

## Environment

Backend loads env from repo-root based on `APP_ENV`:

- `APP_ENV=local` -> `/Users/shreyvishen/ClauseAI/.env.local`
- `APP_ENV=production` -> `/Users/shreyvishen/ClauseAI/.env.production`

Important variables:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET` or `SUPABASE_JWKS_URL`
- `SUPABASE_AUTH_APPROVAL_REQUIRED`
- `SUPABASE_USER_FILES_BUCKET`
- `SUPABASE_BUSINESS_DATA_BUCKET`
- `SUPABASE_STORAGE_REMOTE_ENABLED`
- `BUSINESS_DATA_CACHE_DIR`
- `BUSINESS_DATA_ALLOW_LOCAL_FALLBACK`

## Endpoints

```text
GET    /health
GET    /auth/status
GET    /

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
GET    /api/title_description/generate-metadata/status
GET    /api/title_description/generate-metadata/result

POST   /api/bill_similarity/find-similar
GET    /api/bill_similarity/find-similar/status
GET    /api/bill_similarity/find-similar/result

POST   /api/bill_inspect/inspect

POST   /api/similar_bills_loader/load-similar-bills
GET    /api/similar_bills_loader/load-similar-bills/status
GET    /api/similar_bills_loader/load-similar-bills/result

POST   /api/bill_analysis/analyze-bill
GET    /api/bill_analysis/analyze-bill/status
GET    /api/bill_analysis/analyze-bill/result

POST   /api/conflict_analysis/analyze-conflicts
GET    /api/conflict_analysis/analyze-conflicts/status
GET    /api/conflict_analysis/analyze-conflicts/result

POST   /api/stakeholder_analysis/analyze-stakeholders
GET    /api/stakeholder_analysis/analyze-stakeholders/status
GET    /api/stakeholder_analysis/analyze-stakeholders/result
```

## Storage Migration

Upload `backend/data/**` to `business-data`:

```bash
cd /Users/shreyvishen/ClauseAI/backend
python scripts/upload_business_data.py --resume
```