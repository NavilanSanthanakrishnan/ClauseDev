# Frontend Guide

## Stack
- Vite
- React 19
- React Router
- TanStack Query

## Main Job
- Present the staged ClauseAI workflow clearly and honestly.
- Reflect real persisted backend state rather than optimistic assumptions.
- Keep the drafting workstation usable for long-form bill text.

## Commands
- Dev server: `npm run dev`
- Typecheck: `npm run typecheck`
- Lint: `npm run lint`
- Build: `npm run build`

## Rules
- Do not invent fake completion state for unfinished pipeline stages.
- Guard first-run queries so the app does not spam 404s for artifacts that do not exist yet.
- Keep route coverage in sync with every linked stage path.
- Prefer a guided page-by-page workflow over dashboard clutter.
- Every major page should have one obvious primary action and an explicit next page affordance when the user is in a flow.
- Use plain-language labels before internal product jargon; if the backend says `similar-bills`, the UI can say `Fetch Similar Bills`.
- Navigation should use icons plus short descriptions so the next move is obvious at a glance.
