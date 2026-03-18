# Frontend Lib Guide

## Role
- Shared client-side infrastructure.

## Key Files
- `api.ts`: typed backend access layer
- auth context: local session persistence and protected-route support
- stage metadata: human-readable labels for backend stage keys

## Rules
- Keep API types aligned with backend response shapes.
- Add new endpoints here before wiring them into pages.
- Stage keys should remain canonical and match backend workflow names exactly.
- If a backend endpoint can return `404` during normal first-run usage, the page should gate the query rather than treating that as a console-normal pattern.
- Keep workflow page metadata centralized so navigation labels, ordering, and titles do not drift across screens.
