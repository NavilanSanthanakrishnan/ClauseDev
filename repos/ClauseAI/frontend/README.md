# ClauseAI Frontend

Electron + React frontend for the ClauseAI workflow.

## Overview

The frontend now uses:

- Supabase magic-link authentication
- Bearer-token API calls to backend
- Supabase storage upload for source bill files
- In-memory workflow state synchronized to backend (`/api/workflow/*`)

No browser `localStorage` is used for auth/workflow persistence.

## Development

```bash
cd /Users/shreyvishen/ClauseAI/frontend
npm install
npm run dev           # Web mode
npm run electron:dev  # Desktop mode
```

## Environment

Vite reads env files from repo root (`envDir=..`):

- `/Users/shreyvishen/ClauseAI/.env.local`
- `/Users/shreyvishen/ClauseAI/.env.production`

Important frontend env vars:

- `VITE_API_BASE_URL`
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_SUPABASE_ALLOW_SIGNUP`
- `VITE_SUPABASE_USER_FILES_BUCKET`
- `VITE_LOG_LEVEL`

## Auth Flow

1. User enters email on `/login`.
2. Frontend requests one-time magic link from Supabase.
3. User opens link and returns to `/login`.
4. App captures auth callback token and continues.

Local default: self-signup allowed.
Production default: invite/approval-only (`VITE_SUPABASE_ALLOW_SIGNUP=false`).

## Key Routes

- `/`
- `/login`
- `/api-check`
- `/extraction-input`
- `/extraction-output`
- `/metadata`
- `/similar-bills`
- `/similar-bills-loader`
- `/bill-analysis-report`
- `/bill-analysis-fixes`
- `/legal-analysis-report`
- `/legal-analysis-fixes`
- `/stakeholder-analysis-report`
- `/stakeholder-analysis-fixes`
- `/bill-inspect`
- `/final-report`
- `/final-editing`