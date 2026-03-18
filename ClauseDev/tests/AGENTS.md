# Tests Guide

## Test Layers
- `backend/`: API and workflow content verification
- `e2e/`: Playwright browser coverage

## Expectations
- Backend tests should cover persistence and route behavior without requiring live Codex calls.
- E2E tests should exercise the real app shell and major user flows.
- Manual Playwright MCP testing is valid for debugging real UI regressions and should complement, not replace, scripted tests.

## When Changing Product Flow
- Update tests if the staged workflow changes.
- Keep at least one happy-path project creation flow.
- For major drafting changes, verify export and editor behavior.
