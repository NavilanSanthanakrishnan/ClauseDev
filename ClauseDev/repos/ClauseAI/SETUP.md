# ClauseAI Setup Guide

This guide covers local setup for:

1. Database + Supabase local stack
2. Backend
3. Frontend
4. Full local reset / delete-everything workflow

The commands assume macOS + zsh and project path:

`/Users/shreyvishen/ClauseAI`

## 1. Prerequisites

Install these first:

- Docker Desktop (or Docker-compatible daemon)
- Supabase CLI
- Python 3.13+
- Node.js + npm
- `uv` (recommended for Python package installs)

Check versions:

```bash
supabase --version
node -v
npm -v
uv --version
docker --version
```

## 2. Repo + Environment Files

From repo root:

```bash
cd /Users/shreyvishen/ClauseAI
```

Required env files:

- `.env.local`
- `.env.production`

For local development, verify these in `.env.local`:

- `APP_ENV=local`
- `SUPABASE_URL=http://127.0.0.1:54321`
- `SUPABASE_ANON_KEY=...`
- `SUPABASE_SERVICE_ROLE_KEY=...`
- `SUPABASE_JWT_SECRET=...`
- `SUPABASE_JWKS_URL=http://127.0.0.1:54321/auth/v1/.well-known/jwks.json`
- `VITE_SUPABASE_URL=http://127.0.0.1:54321`
- `VITE_SUPABASE_ANON_KEY=...`
- `VITE_API_BASE_URL=http://localhost:8000`

If keys are stale, regenerate from running local Supabase:

```bash
cd /Users/shreyvishen/ClauseAI
supabase status -o env
```

Then copy the reported keys into `.env.local`.

## 3. Database / Supabase Local Setup

### 3.1 Start local Supabase

```bash
cd /Users/shreyvishen/ClauseAI
supabase start
```

This applies migrations in `supabase/migrations/` automatically.

### 3.2 Verify stack is healthy

```bash
cd /Users/shreyvishen/ClauseAI
supabase status
```

Expected services/URLs include:

- API: `http://127.0.0.1:54321`
- Studio: `http://127.0.0.1:54323`
- DB: `postgresql://postgres:postgres@127.0.0.1:54322/postgres`

### 3.3 Buckets and schema

Current migration creates:

- Tables: `app_users`, `user_workflows`, `workflow_history`, `user_files`
- Buckets: `business-data`, `user-files`
- RLS policies for authenticated access and ownership

## 4. Backend Setup

### 4.1 Create/activate virtualenv

```bash
cd /Users/shreyvishen/ClauseAI/backend
uv venv --python 3.13
source .venv/bin/activate
```

### 4.2 Install dependencies

```bash
cd /Users/shreyvishen/ClauseAI/backend
source .venv/bin/activate
uv pip install -r requirements.txt
```

If needed, install explicitly:

```bash
cd /Users/shreyvishen/ClauseAI/backend
source .venv/bin/activate
uv pip install supabase 'PyJWT[crypto]' ...
```

### 4.3 Start backend

```bash
cd /Users/shreyvishen/ClauseAI/backend
source .venv/bin/activate
APP_ENV=local python main.py
```

Backend runs on `http://localhost:8000`.

### 4.4 Quick backend check

In another terminal:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/auth/status
```

## 5. Frontend Setup

### 5.1 Install frontend dependencies

```bash
cd /Users/shreyvishen/ClauseAI/frontend
npm install
```

### 5.2 Start frontend

Web mode:

```bash
cd /Users/shreyvishen/ClauseAI/frontend
npm run dev
```

Electron mode:

```bash
cd /Users/shreyvishen/ClauseAI/frontend
npm run electron:dev
```

### 5.3 Auth flow

- Open `/login`
- Enter email
- Use magic link from local Mailpit (`http://127.0.0.1:54324`) or configured email provider

Local config currently allows signup (`VITE_SUPABASE_ALLOW_SIGNUP=true`).

## 6. First-Time Business Data Upload (Required)

The backend corpus (`backend/data/**`) must be uploaded to Supabase storage bucket `business-data` for full storage-backed operation.

Run once:

```bash
cd /Users/shreyvishen/ClauseAI/backend
source .venv/bin/activate
APP_ENV=local python scripts/upload_business_data.py --resume
```

Useful options:

```bash
# preview only
APP_ENV=local python scripts/upload_business_data.py --dry-run

# custom state file
APP_ENV=local python scripts/upload_business_data.py --resume --state-file /tmp/business_upload_state.json
```

State/progress file:

- `backend/.cache/business_data_upload_state.json`

## 7. End-to-End Smoke Test Checklist

Run in order:

1. `supabase start`
2. backend: `APP_ENV=local python main.py`
3. frontend: `npm run dev`
4. login via magic link
5. upload a file on `/extraction-input`
6. confirm extraction + subsequent workflow stages load

Optional build/compile checks:

```bash
cd /Users/shreyvishen/ClauseAI
source backend/.venv/bin/activate
python -m compileall backend/app backend/main.py
cd /Users/shreyvishen/ClauseAI/frontend && npm run build
```

## 8. How To Delete / Reset Everything (Local)

This section includes destructive commands for local dev state.

## 8.1 Stop all running services

```bash
cd /Users/shreyvishen/ClauseAI
supabase stop
```

Stop backend/frontend terminals with `Ctrl+C`.

## 8.2 Reset local Supabase database + storage state

This wipes local Postgres data and storage objects for the project.

```bash
cd /Users/shreyvishen/ClauseAI
supabase db reset
```

If you want to fully tear down containers and volumes used by local Supabase:

```bash
cd /Users/shreyvishen/ClauseAI
supabase stop --all
```

Then (optional) remove local Supabase docker resources manually:

```bash
docker ps -a --filter "name=supabase_"
docker volume ls | rg supabase
# remove specific project containers/volumes if needed
```

## 8.3 Delete local upload/cache artifacts only

```bash
cd /Users/shreyvishen/ClauseAI
rm -rf backend/.cache
rm -rf backend/tests/outputs
rm -rf frontend/dist
```

## 8.4 Delete local dependency installs only

```bash
cd /Users/shreyvishen/ClauseAI
rm -rf backend/.venv
rm -rf frontend/node_modules
```

## 8.5 Full local project clean (keep git repo)

```bash
cd /Users/shreyvishen/ClauseAI
rm -rf backend/.venv frontend/node_modules frontend/dist backend/.cache backend/tests/outputs
supabase stop --all
```

## 8.6 Nuclear option: delete the entire local repo directory

Only do this if you intentionally want to remove all local project files.

```bash
cd /Users/shreyvishen
rm -rf /Users/shreyvishen/ClauseAI
```

## 8.7 Also remove local Colima/Docker dev VM state (optional)

If you use Colima and want a full VM reset:

```bash
colima stop
colima delete
```

If you use Docker Desktop and want to prune unused resources:

```bash
docker system prune -a --volumes
```

## 9. Rebuild From Zero After Deletion

1. Clone repo again (if deleted).
2. Recreate `.env.local` / `.env.production`.
3. `supabase start`.
4. Recreate backend venv + install deps.
5. `npm install` in frontend.
6. Run `upload_business_data.py --resume`.
7. Start backend/frontend and run smoke test.