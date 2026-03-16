# ClauseDev

ClauseDev currently contains Step1, a standalone bill-similarity app built on top of a local OpenStates PostgreSQL restore.

Upload a bill as `pdf`, `docx`, or `txt`, and the app returns similar bills from the OpenStates corpus through a hybrid retrieval pipeline:

1. Extract and normalize the uploaded bill text.
2. Use Codex OAuth with `gpt-5.4` to build a structured bill profile.
3. Search a prebuilt OpenStates bill index with PostgreSQL full-text search.
4. Rerank the candidate set locally with sentence-transformer embeddings.
5. Run a final Codex rerank focused on policy intent, legal mechanism, and affected entities.

## Repository Layout

- `step1/app.py`: FastAPI app and HTML UI endpoints
- `step1/services/`: extraction, Codex OAuth, database access, retrieval, reranking
- `step1/templates/`: simple browser UI
- `step1/static/`: frontend assets
- `sql/bootstrap_openstates_step1.sql`: search table and index bootstrap
- `scripts/bootstrap_db.py`: applies the SQL bootstrap
- `scripts/download_embedding_model.py`: pre-downloads the embedding model
- `scripts/export_sample_bills.py`: exports sample bills from OpenStates
- `scripts/smoke_test.py`: quick local API check

## Requirements

- Python `3.11+`
- PostgreSQL reachable at `127.0.0.1:55432`
- OpenStates database: `openstates_public_compat`
- Valid Codex OAuth session available locally

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/bootstrap_db.py
python scripts/download_embedding_model.py
python scripts/export_sample_bills.py
```

## Run

```bash
source .venv/bin/activate
uvicorn step1.app:app --host 127.0.0.1 --port 8011
```

Then open [http://127.0.0.1:8011](http://127.0.0.1:8011).

## Smoke Test

With the server running:

```bash
source .venv/bin/activate
python scripts/smoke_test.py samples/wildfire.txt
```

## Configuration

Local runtime settings live in `.env`. Commit `.env.example`, not `.env`.

Important variables:

- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`
- `CODEX_MODEL`
- `LEXICAL_CANDIDATE_LIMIT`
- `SEMANTIC_INPUT_LIMIT`
- `LLM_RERANK_INPUT_LIMIT`
- `FINAL_RESULT_LIMIT`

## Search Design

The system is intentionally hybrid:

- lexical retrieval for high recall
- local semantic reranking for contextual similarity
- Codex final reranking for policy/mechanism judgment

That is the practical path for a large legislative corpus: use indexed retrieval to narrow the search space, then spend model reasoning on the top candidates instead of the full database.
