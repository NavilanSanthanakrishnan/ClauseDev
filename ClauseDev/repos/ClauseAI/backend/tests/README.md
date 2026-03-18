# ClauseAI Backend Test Suite

Integration-style scripts for validating the live API pipeline.

## Prerequisites

1. Start local Supabase stack:

```bash
cd /Users/shreyvishen/ClauseAI
supabase start
```

2. Start backend server:

```bash
cd /Users/shreyvishen/ClauseAI/backend
source .venv/bin/activate
APP_ENV=local python main.py
```

3. Configure test auth (repo-root `.env.local` or shell env):

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_TEST_EMAIL`
- `SUPABASE_TEST_PASSWORD`
- Optional: `SUPABASE_TEST_AUTO_SIGNUP=true`
- Optional override: `SUPABASE_TEST_ACCESS_TOKEN`

4. Ensure sample input file exists:

- `/Users/shreyvishen/ClauseAI/backend/tests/samples/bill.pdf`

## Run Order

```bash
cd /Users/shreyvishen/ClauseAI/backend/tests
python test_0_root.py
python test_1_health.py
python test_2_bill_extraction.py
python test_3_title_description.py
python test_4_bill_similarity.py
python test_5_bill_inspect.py
python test_5_similar_bills_loader.py
python test_6_bill_analysis.py
python test_7_conflict_analysis.py
python test_8_stakeholder_analysis.py
```

## Notes

- Protected endpoints use bearer auth (`Authorization: Bearer <token>`).
- Loader/analysis/conflict/stakeholder tests poll async status endpoints.
- Phase-based tests still run report + fixes cycles for final three stages.

