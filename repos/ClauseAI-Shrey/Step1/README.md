# Step1

Step1 is the current working retrieval and editing slice inside the Clause repository.

It is a standalone FastAPI app built on top of an existing local OpenStates PostgreSQL database. The app now combines:

1. Step 1 and Step 2 retrieval:
   - extract the uploaded bill
   - wait for the user to trigger metadata generation
   - build an editable semantic profile with Codex OAuth `gpt-5.4`
   - retrieve similar bills from OpenStates with live progress updates
   - rerank them locally and with a final Codex judge
2. A live Codex editing loop:
   - create a per-session workspace for the uploaded draft
   - launch a local `codex app-server` thread against that workspace only after retrieval context is ready
   - stream Codex commentary, commands, and diff approvals into the browser
3. Step 3, Step 4, and Step 5 editing inside the same loop:
   - start with a basic Step 3 cleanup pass on the user draft alone
   - move into Step 4 only after Step 3 is done
   - use similar passed bills plus structured short summaries as source context for targeted strengthening
   - move into Step 5 only after Step 4 is done
   - run web-backed stakeholder investigation, write a structured stakeholder report, then use it for narrow politically and operationally viable bill edits
   - require explicit approve or reject before any draft file change lands

## Current Scope

This step is still an MVP slice, not the final Clause product.

- good for: interactive upload, similarity retrieval, and a visible Codex approval loop
- not yet guaranteed: exhaustive recall of every materially related bill
- not yet included: auth, multi-user persistence, long-running background jobs, production deployment
- roadmap for higher accuracy and lower latency: see [`FUTURE.md`](FUTURE.md)

## Repository Layout

- `step1/app.py`: FastAPI app and workflow API endpoints
- `step1/models.py`: search models plus live Codex workflow session models
- `step1/services/similar_bills.py`: extraction, profiling, retrieval, semantic reranking, final reranking
- `step1/services/workflow_service.py`: session lifecycle orchestration
- `step1/services/codex_app_server.py`: local `codex app-server` launcher and per-session thread bridge
- `step1/services/workflow_context.py`: Step 4 source-bill staging from retrieval results and `clauseai_bill_table`
- `step1/services/workflow_store.py`: on-disk workflow session persistence
- `step1/templates/`: browser UI
- `step1/static/`: frontend assets
- `sql/bootstrap_openstates_step1.sql`: search table and index bootstrap
- `scripts/bootstrap_db.py`: applies the SQL bootstrap
- `scripts/download_embedding_model.py`: pre-downloads the embedding model
- `scripts/export_sample_bills.py`: exports sample bills from OpenStates
- `scripts/smoke_test.py`: quick local API check

## Requirements

- Python `3.11+`
- PostgreSQL reachable at `127.0.0.1:55432`
- OpenStates database: `openstates` by default, or any database that already contains the `public.opencivicdata_*` tables
- Valid Codex OAuth session available locally
- Local `codex` CLI installed and available on `PATH`

Optional but recommended for richer Step 4 context:

- `public.clauseai_bill_table` populated in the same database
- `clean_json_full_bill_text` or `clean_yaml_full_bill_text` available on `clauseai_bill_table`

If `clauseai_bill_table` is missing, Step 4 still runs, but source-bill context falls back to the Step1 retrieval excerpts and raw bill text.

Step 5 depends on the live Codex loop having access to web search. The stakeholder analysis stage writes both:

- `context/stakeholder_report.json`
- `context/stakeholder_report.md`

Those files are generated inside the session workspace and updated automatically by Codex before Step 5 bill edits are proposed.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python scripts/bootstrap_db.py
python scripts/download_embedding_model.py
python scripts/export_sample_bills.py
```

`bootstrap_db.py` does not load OpenStates data for you. It expects your target database to already contain the OpenStates tables and then builds the Step1 retrieval objects inside that same database:

- schema: `step1`
- table: `step1.bill_search_docs`
- view: `step1.bill_lookup`
- supporting GIN, trigram, and btree indexes

If your database name is not `openstates`, set `POSTGRES_DB` in `.env` before running the bootstrap.

For Codex-backed bill profiling, reranking, and Step 3/4 workflow suggestions, make sure your local Codex session is already authenticated:

```bash
codex login
```

The browser editing loop also depends on the local app-server transport that ships with the CLI. Step1 will reuse an already-running local app-server if one is listening on `CODEX_APP_SERVER_PORT`; otherwise it will start one for you.

## Run

```bash
source .venv/bin/activate
uvicorn step1.app:app --host 127.0.0.1 --port 8011
```

Then open [http://127.0.0.1:8011](http://127.0.0.1:8011).

## Browser Workflow

The UI now follows the intended Clause editing loop:

1. Upload a bill.
2. Click to generate metadata.
3. Review and edit the generated metadata.
4. Start similar-bill search and watch live retrieval updates.
5. Review the analogs, scores, source links, and staged Step 4 source bills.
6. Once retrieval finishes, Codex starts the editing loop on the same session.
7. Review any pending draft diff in the approval card.
8. Approve or reject the diff.
9. After Step 4, Codex performs a Step 5 stakeholder pass: web-backed investigation, structured stakeholder report generation, and then targeted bill edits tied back to that report.
10. Use the feedback box at any point to steer the active turn.
11. Download the current draft at any point.

The server stores each workflow session on disk under `uploads/workflow_sessions/`.

## API Surface

Main endpoints:

- `POST /api/search`
  - legacy alias for upload-only session creation
- `POST /api/workflow/upload`
  - uploads the bill
  - extracts text
  - creates and returns the workflow session
- `POST /api/workflow/{session_id}/metadata/generate`
  - runs Codex metadata generation for the uploaded bill
- `POST /api/workflow/{session_id}/metadata`
  - saves user-edited bill metadata
- `POST /api/workflow/{session_id}/similar-bills/start`
  - starts live similar-bill retrieval from the saved metadata
- `GET /api/workflow/{session_id}`
  - returns the current workflow session
- `GET /api/workflow/{session_id}/stream`
  - streams live workflow session snapshots as server-sent events
- `POST /api/workflow/{session_id}/approve`
  - accepts the current pending Codex diff
- `POST /api/workflow/{session_id}/reject`
  - declines the current pending Codex diff and lets Codex continue
- `POST /api/workflow/{session_id}/steer`
  - sends human feedback into the active Codex turn, or starts a new turn if the previous one finished
- `GET /api/workflow/{session_id}/draft`
  - downloads the current draft text

## Smoke Test

With the server running:

```bash
source .venv/bin/activate
python scripts/smoke_test.py samples/wildfire.txt
```

That smoke test validates workflow session creation and bill extraction. It does not yet walk metadata generation, live similar-bill search, or the Step 3, Step 4, and Step 5 approval loop.

## Configuration

Local runtime settings live in `.env`. Commit `.env.example`, not `.env`.

Important variables:

- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`
- `CODEX_MODEL`
- `LEXICAL_CANDIDATE_LIMIT`
- `SEMANTIC_INPUT_LIMIT`
- `LLM_RERANK_INPUT_LIMIT`
- `FINAL_RESULT_LIMIT`
- `MAX_WORKFLOW_BILL_CHARS_FOR_LLM`
- `MAX_SOURCE_BILL_CHARS_FOR_LLM`
- `MAX_SOURCE_BILLS_FOR_WORKFLOW`
- `CODEX_APP_SERVER_HOST`
- `CODEX_APP_SERVER_PORT`

## Search and Editing Design

The system is intentionally hybrid:

- lexical retrieval for high recall
- local semantic reranking for contextual similarity
- Codex final reranking for policy and mechanism judgment
- local `codex app-server` for the live approval-gated editing loop
- live web-backed Step 5 stakeholder investigation before politically and operationally targeted edits

That architecture keeps search indexed and cheap while reserving model reasoning for:

- the upload profile
- the final top candidate rerank
- one reviewable file diff at a time in the user workflow
- stakeholder analysis artifacts and evidence-backed Step 5 optimization planning

## Future Work

The detailed roadmap for pushing retrieval quality and latency much further is in [`FUTURE.md`](FUTURE.md).
