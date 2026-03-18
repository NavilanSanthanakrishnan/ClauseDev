# Clause Memory

## Product Direction
- `Clause` is a desktop-first legislative drafting system, not just a search UI.
- The product has four core surfaces:
  - `Bills`: workspace home for draft projects
  - `Bill Lookup`: bill retrieval and comparison
  - `Law Lookup`: statute retrieval and contradiction tracing
  - `Workspace`: bill editing, supporting intelligence, and the on-site agent
- The product should feel editorial, calm, and procedural. It should never feel game-like.

## User Promise
- Users should be able to move from research into drafting without changing tools.
- Search results must show why they matched.
- The workspace must keep:
  - similar bills
  - conflicting laws
  - stakeholder pressure
  - next drafting actions
  - the agent conversation
  in one place around the draft text.

## Auth
- Auth is env-gated from the backend.
- When auth is enabled, the UI must block the product behind the login screen.
- Current local setup uses a dummy account so the auth template can later be replaced with real identity providers.

## Search Principles
- Standard search is for exact, filter-driven retrieval.
- Agentic search is for intent-driven discovery and should orchestrate hybrid retrieval, not replace it.
- Bill and law retrieval should stay evidence-backed and auditable.
- Fast local lexical retrieval plus semantic boosts and reranking are the baseline.

## Orchestration Principles
- The agent in the workspace is not a chatbot bolted onto the side.
- It should operate over concrete tools:
  - bill search
  - law search
  - stakeholder analysis
  - drafting suggestions
- The user should understand what the agent is doing and what evidence it used.

## YC / Survival Lens
- The defensible product is not passive bill tracking.
- The wedge is offensive legislative intelligence: helping small policy teams draft, compare, and revise bills faster with citations and strategic context.
- The highest-value workflow is the bill workspace, because that is where research converts into output.

## Current Gaps After This Checkpoint
- More state law corpora beyond California and U.S. Code
- Stronger evidence compression in the workspace rail
- Export / collaboration workflow
- Real auth provider integration
- More explicit citations inside agent replies

## Checkpoint Rule
- After each meaningful checkpoint:
  1. run backend tests
  2. run frontend build
  3. run the live smoke test
  4. sync into the nested `ClauseDev` repo with `python3 scripts/checkpoint_to_clausedev.py --commit "..." --push`
