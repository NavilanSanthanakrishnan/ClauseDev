# Testing And Quality

## Non-Negotiable Rule

Testing happens after every meaningful step, not at the end.

This is directly aligned with `prompts/test-prompt.md`.

## Testing Layers

### 1. Unit tests

- parsers
- DB adapters
- auth helpers
- prompt validators
- suggestion application logic

### 2. Integration tests

- API routes against real Postgres
- ingestion pipeline smoke tests
- worker step orchestration
- draft version restore flows

### 3. End-to-end tests

- login/signup
- create project
- upload bill
- complete pipeline stages
- open editor
- accept/reject suggestion
- export draft

### 4. Human-perspective tests

- UI clarity
- route transitions
- report readability
- keyboard and resize behavior

## Playwright Requirement

The user explicitly requested Playwright MCP for frontend testing.

Plan:

- use Playwright MCP interactively during implementation to verify real flows and catch layout regressions early
- also check in native Playwright test specs for CI and repeatability

## Backend Test Plan

- `pytest` for unit and integration coverage
- temporary Postgres databases for test isolation
- fixture-based stage testing for each workflow service
- golden artifact tests for prompt outputs where feasible

## Data Validation Tests

For `"clauseai-db"`:

- import count checks
- null/coverage checks on required fields
- search query smoke tests
- citation lookup smoke tests
- canonical legal index integrity checks

For `"clauseai-db-user"`:

- auth token lifecycle tests
- refresh token rotation tests
- project/workflow persistence tests
- version-restore tests

## Frontend Test Plan

- component tests for key UI primitives
- page-level tests for major route shells
- Playwright full-flow tests
- responsive snapshots for the main shell and editor

## Desktop Packaging Tests

- Electron dev boot
- macOS package smoke test
- Windows package smoke test
- preload bridge contract tests

## Regression Gates

Before moving from one milestone to the next:

- new feature tests pass
- affected previous tests rerun
- one human-perspective pass completes the changed flow
- no known failing tests are left parked

## Release Gate

Do not call a milestone done unless:

- backend tests pass
- frontend tests pass
- Playwright happy-path flow passes
- at least one manual inspection of the changed surface is done
- logs show no unresolved runtime failures
