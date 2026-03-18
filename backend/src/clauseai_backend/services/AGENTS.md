# Services Guide

## What Lives Here
- Prompt loading
- Codex auth and API client behavior
- Extraction/parsing
- Analysis generation
- Drafting agent behavior
- Chat/research behavior
- Export helpers

## Rules
- Keep prompt-backed outputs structured first, markdown second.
- Every model-backed path should degrade cleanly when the model is unavailable.
- Do not scatter prompt names or parsing rules across unrelated modules.
- Keep source references attributable when generating suggestions or reports.

## Quality Bar
- Similar-bills output should connect precedent to concrete drafting changes.
- Legal output should cite exact sections and explain conflict logic.
- Stakeholder output should identify opposition and language shifts, not just summarize.
- Editor output should generate drafting strategy plus actionable patch-style suggestions.
