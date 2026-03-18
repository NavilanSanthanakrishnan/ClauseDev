# Frontend Source Guide

## Directory Roles
- `components/`: reusable layout and framing pieces
- `lib/`: API client, auth context, constants, stage metadata
- `pages/`: route-level product surfaces

## Working Rules
- Route pages should own page-specific queries and mutations.
- Shared fetch utilities belong in `lib/api.ts`.
- Keep auth and navigation behavior consistent across all protected routes.
- When a backend concept is stage-driven, use the exact backend stage keys in the UI.
- Treat `lib/stages.ts` as the source of truth for workflow page order and labels.
- Favor page-level clarity over compression: split guidance across route surfaces instead of overloading one screen.
- Preserve the product shell hierarchy:
  landing/auth -> sidebar app shell -> Your Bills / Bills Database / Laws Database / Agentic Chatbot -> staged drafting workflow.
- Keep the workflow pages explicit and purpose-built. Do not collapse the drafting flow back into one generic stage screen.
- The final editor must keep analysis visible while the live Codex session runs. It is not a plain text area plus detached suggestions.
- Pre-editor workflow pages show analysis and general drafting guidance only. The UI must not imply that those pages already generated approved bill text changes.
- Keep the black-and-ivory visual system restrained, sparse, and serious; avoid generic SaaS gradients or dashboard clutter.
