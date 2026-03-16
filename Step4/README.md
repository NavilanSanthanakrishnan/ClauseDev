# Step4

Step4 is the bill-to-law conflict finder.

Goal:

- upload a bill
- identify the bill's key details, including its country of origin
- retrieve candidate California and federal statutes
- determine which statutes actually conflict with the bill
- return the exact citations, quoted text, and an explanation of the conflict

This app uses:

- Codex OAuth `gpt-5.4` for bill profiling and final conflict judgment
- PostgreSQL `california_code` for California statutes
- PostgreSQL `uscode_local` for federal U.S. Code sections and provisions
- local semantic reranking to narrow candidate statutes before the final LLM pass
- amendment-aware conflict detection for bills that expressly change current California code sections
- deterministic wage-and-hour conflict rules as a safety net for obvious statute collisions

## Setup

```bash
cd /Users/navilan/Documents/Clause/Step4
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Bootstrap Search Indexes

This adds the search indexes and helper views Step4 expects on the California and federal databases.

```bash
cd /Users/navilan/Documents/Clause/Step4
source .venv/bin/activate
python scripts/bootstrap_legal_search.py
```

## Run

```bash
cd /Users/navilan/Documents/Clause/Step4
source .venv/bin/activate
uvicorn step4.app:app --host 127.0.0.1 --port 8012
```

Then open [http://127.0.0.1:8012](http://127.0.0.1:8012).

## Test

Unit tests:

```bash
cd /Users/navilan/Documents/Clause/Step4
source .venv/bin/activate
pytest -q
```

API smoke tests with the included synthetic bills:

```bash
cd /Users/navilan/Documents/Clause/Step4
source .venv/bin/activate
python scripts/smoke_test.py samples/overtime_conflict.txt
python scripts/smoke_test.py samples/minimum_wage_conflict.txt
```

Official California benchmark cases from OpenStates:

```bash
cd /Users/navilan/Documents/Clause/Step4
source .venv/bin/activate
python -u scripts/run_official_benchmarks.py --skip-agent
```

This benchmark suite uses real California bills from the local `openstates_public_compat` database and checks the returned conflicts against expected current-code collisions. The benchmark metadata lives in [`/Users/navilan/Documents/Clause/Step4/benchmarks/official_cases.json`](/Users/navilan/Documents/Clause/Step4/benchmarks/official_cases.json).

Codex reviewer loop:

```bash
cd /Users/navilan/Documents/Clause/Step4
source .venv/bin/activate
python -u scripts/run_official_benchmarks.py --max-agent-attempts 10
```

The review loop uses the `TestingAgent` service to ask Codex whether the returned conflicts are accurate. This is useful for audit, but it can fail on very large review payloads; when that happens the script stops after the configured attempt limit.

## Expected Databases

- California: `california_code`
- Federal: `uscode_local`

Default connection details are in `.env.example`.

## Notes

- California already has a section-level search corpus from Step2.
- Step4 adds dedicated legal-search indexes for the federal U.S. Code corpus so retrieval stays fast enough for interactive use.
- The local sentence-transformer reranker is now loaded with `local_files_only=True` so benchmark runs do not depend on live Hugging Face availability.
- The app is designed around staged retrieval:
  1. profile the uploaded bill
  2. retrieve likely California and federal statutes
  3. semantically rerank them
  4. use Codex to decide which are actual conflicts
  5. apply deterministic pattern-based backstops for obvious wage/hour conflicts that should never be missed
