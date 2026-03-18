# Pages Guide

## Role
- Each file here is a route-level product surface.
- Pages should be understandable in terms of the user workflow, not generic component decomposition.

## Expectations
- `BillsHomePage`: create/resume workspaces
- `ProjectStagePage`: staged analysis flow
- `EditorPage`: versioned drafting workstation
- database pages: reference search surfaces
- chat page: research and drafting support

## Guardrails
- Do not hide the next step in the workflow.
- If a page links to a route, that route must exist.
- Show explicit pending/error/empty states.
- Avoid prefetching artifacts that are impossible to exist on first load.
- Use plain headers and descriptions that a first-time user can understand without product context.
- When a page belongs to the drafting flow, include clear page-to-page navigation with explicit wording such as `Next Page (Fetch Similar Bills)`.
