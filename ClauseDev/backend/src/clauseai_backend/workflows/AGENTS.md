# Workflow Engine Guide

## Role
- Owns persisted stage execution for metadata, similar-bills, legal, stakeholders, and editor-related runs.
- Responsible for run creation, status transitions, completion/error recording, and artifact persistence.

## Invariants
- A pipeline run must always end in a persisted terminal state.
- Errors must include a summary that the UI can render directly.
- Stage execution should be safe to inspect after the fact from stored artifacts and suggestions.

## When Editing
- Preserve deterministic stage naming; the frontend depends on it.
- Do not create hidden stages without updating route/UI assumptions.
- If adding retries or async workers later, maintain current persisted semantics so existing UI remains valid.
