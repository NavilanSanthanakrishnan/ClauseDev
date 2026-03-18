# ClauseAI Deployment Guide

## How the env files work

| File | Purpose | Read by |
|---|---|---|
| `.env.local` (repo root) | Local dev config | Backend (`APP_ENV=local`) + Vite (`envDir: '..'`) |
| `.env.production` (repo root) | Production config | Backend (`APP_ENV=production`) + Vite (production builds) |
| `backend/.env` | Backend-only overrides (CORS, rate limits, HF token, basic auth) | Backend only (via `python-dotenv`) |
| `backend/.env.keys` | One OpenRouter API key per line (load-balanced) | Backend only at startup |

**The env selection logic** lives in `backend/app/core/env_loader.py`:
- `APP_ENV=local` → reads `.env.local` from repo root
- `APP_ENV=production` → reads `.env.production` from repo root

Vite reads from the same repo root (`envDir: '..'` in `vite.config.js`), so both frontend and backend share the same root env files.

---

## 1. Supabase Setup (Production)

### Create a Supabase project
1. Go to [supabase.com](https://supabase.com), create a new project
2. Note your **Project URL**, **anon key**, **service role key**, and **JWT secret** from Settings > API

### Run the migration
```bash
# Install Supabase CLI if you haven't
brew install supabase/tap/supabase

# Link to your remote project
supabase link --project-ref <your-project-ref>

# Push the migration (creates tables + storage buckets)
supabase db push
```

This creates:
- Tables: `app_users`, `user_workflows`, `workflow_history`, `user_files` (all with RLS)
- Storage buckets: `business-data` (backend corpus), `user-files` (user uploads)

### Upload business data
```bash
cd backend
python scripts/upload_business_data.py --resume
```
This uploads everything in `backend/data/` to the `business-data` Supabase Storage bucket.

---

## 2. Configure `.env.production`

Fill in the real values:

```ini
APP_ENV=production

# Backend API (wherever you deploy the FastAPI server)
VITE_API_BASE_URL=https://api.your-domain.com

# Supabase (from your Supabase dashboard)
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_ANON_KEY=eyJ...your_real_anon_key
SUPABASE_SERVICE_ROLE_KEY=eyJ...your_real_service_role_key
SUPABASE_JWT_SECRET=your_real_jwt_secret
SUPABASE_JWKS_URL=https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json

# Frontend Supabase (VITE_ prefix = baked into frontend build)
VITE_SUPABASE_URL=https://<project-ref>.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...your_real_anon_key
VITE_SUPABASE_ALLOW_SIGNUP=false
VITE_SUPABASE_USER_FILES_BUCKET=user-files

# Storage
SUPABASE_AUTH_APPROVAL_REQUIRED=true
SUPABASE_USER_FILES_BUCKET=user-files
SUPABASE_BUSINESS_DATA_BUCKET=business-data
SUPABASE_STORAGE_REMOTE_ENABLED=true
BUSINESS_DATA_ALLOW_LOCAL_FALLBACK=false
BUSINESS_DATA_CACHE_DIR=.cache/business-data

# LLM
OPENROUTER_API_KEY=sk-or-v1-...your_key
DEFAULT_MODEL=stepfun/step-3.5-flash:free

# Logging
VITE_LOG_LEVEL=info
LOG_LEVEL=INFO
```

### Also update `backend/.env` for production:
```ini
CORS_ALLOW_ORIGINS=https://your-frontend-domain.com
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_WINDOW_SECONDS=60
LOG_LLM_OUTPUTS=false
LOG_LLM_PROMPTS=false
```

### `backend/.env.keys`
Put your OpenRouter API keys here, one per line. The backend shuffles them at startup for load balancing. If you only have one key, just put the single key.

---

## 3. Deploy the Backend (FastAPI)

The backend is a standard FastAPI app with no Dockerfile.

### Option A: Railway / Render / Fly.io

**Railway** (easiest):
```bash
# Install Railway CLI
npm i -g @railway/cli

# Login and init
railway login
railway init

# Set env vars (copy from .env.production + backend/.env)
railway variables set APP_ENV=production
railway variables set SUPABASE_URL=https://...
railway variables set OPENROUTER_API_KEY=sk-or-v1-...
# ... set ALL the env vars from .env.production

# Deploy
railway up
```

**Start command** Railway/Render should use:
```bash
cd backend && pip install -r requirements.txt && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Python version**: 3.11+ (needs `transformers`, `torch`, `sentence-transformers`)

> **Heads up**: This backend pulls in `torch` and `sentence-transformers` which are heavy (~2GB). Make sure your deployment platform supports large slugs. Railway and Render both handle this fine.

### Option B: VPS (DigitalOcean / EC2 / etc.)

```bash
# On your VPS
git clone <your-repo>
cd ClauseAI

# Copy your env files
# .env.production at repo root
# backend/.env and backend/.env.keys in backend/

# Install Python deps
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install playwright browsers (needed for web scraping)
playwright install chromium

# Download NLTK data
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"

# Run with systemd or supervisor
APP_ENV=production uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Put it behind **nginx** or **caddy** for HTTPS:
```nginx
server {
    listen 443 ssl;
    server_name api.your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 600s;  # long timeout for LLM calls
    }
}
```

---

## 4. Deploy the Frontend

Two options: Electron desktop app or web-only.

### Option A: Electron Desktop App (distribute as .dmg / .exe)

```bash
cd frontend

# Build for Mac
APP_ENV=production npm run package:mac
# Output: frontend/release/*.dmg

# Build for Windows
APP_ENV=production npm run package:win
# Output: frontend/release/*.exe
```

The `VITE_*` env vars get baked in at build time. Make sure `.env.production` is in the repo root before building.

### Option B: Web-only (Vercel / Netlify / static hosting)

Since Vite builds to `frontend/dist/` as static files:

```bash
cd frontend

# Build
VITE_API_BASE_URL=https://api.your-domain.com \
VITE_SUPABASE_URL=https://<project-ref>.supabase.co \
VITE_SUPABASE_ANON_KEY=eyJ...key \
npm run build

# Output is in frontend/dist/
```

Then deploy `frontend/dist/` to any static host. On **Vercel**:
```bash
cd frontend
npx vercel --prod
```

Or **Netlify**: point it at `frontend/` with build command `npm run build` and publish dir `dist`.

> **Note**: The `base: './'` in vite config uses relative paths (for Electron `file://`). For web hosting this works fine, but if you want clean URLs with client-side routing, add a redirect rule (e.g., `_redirects` for Netlify: `/* /index.html 200`).

---

## 5. Post-deploy checklist

| Step | What to do |
|---|---|
| Supabase Auth | Configure redirect URLs in Supabase dashboard: `https://your-frontend-domain.com` |
| CORS | Set `CORS_ALLOW_ORIGINS` in `backend/.env` to your frontend URL |
| User approval | If `SUPABASE_AUTH_APPROVAL_REQUIRED=true`, manually set `approved=true` in `app_users` table for users |
| Health check | Hit `GET https://api.your-domain.com/health` to verify backend is up |
| API keys | Make sure `backend/.env.keys` has your OpenRouter keys (or set `OPENROUTER_API_KEY` as env var) |
| Playwright | Run `playwright install chromium` on your server (needed for web scraping features) |
| NLTK data | Run `python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"` |

---

## Quick reference: what goes where

```
VITE_*  variables           →  baked into frontend JS at build time (public, visible to users)
SUPABASE_SERVICE_ROLE_KEY   →  backend only (NEVER expose to frontend)
OPENROUTER_API_KEY          →  backend only
SUPABASE_JWT_SECRET         →  backend only
SUPABASE_ANON_KEY           →  both (it's designed to be public, RLS protects data)
```

**Security rule**: Only `VITE_` prefixed vars end up in the frontend bundle. Everything else stays server-side.
