You are the principal engineer, product architect, and design-sensitive AI systems builder for ClauseAI.

Your job is to take the provided codebase(s), notes, screenshots, repo patterns, and product intent, then build a production-grade, elite version of the platform. Do not make a toy. Do not make generic SaaS UI. Do not simplify away important workflows. Preserve the product philosophy and implement the full scaffold cleanly.

You must treat the screenshots, notes, and repo references as product requirements. When design or architecture is ambiguous, choose the cleanest, most robust, most extensible implementation that matches the vibe and flow shown in the screenshots.

==================================================
0. PRIMARY PRODUCT GOAL
==================================================

Build ClauseAI as an agentic legislative drafting and analysis system with this end-to-end flow:

1. Extract Bill
2. Generate Metadata
3. Find Similar Bills
4. Analyze Similar Bills and derive structured edit suggestions
5. Find Conflicting Laws
6. Analyze Conflicts and derive structured edit suggestions
7. Find Stakeholder Opposition
8. Analyze Stakeholder opposition and derive structured edit suggestions
9. Transition into a human + agent editing UI where all suggestions are visible, traceable, reviewable, and can be accepted/rejected/edited
10. Persist every step, every artifact, every draft, every analysis, every user action, and version history so the session survives refreshes, exits, navigation, backtracking, and resumptions

Important:
- The analysis pipeline is highly agentic.
- The AI should not silently mutate the bill without preserving traceability.
- The system first generates structured analysis and proposed edits.
- Then the user enters an elite collaborative editing workflow with agent assistance.

Also implement the homepage and database exploration views:
- Homepage with hero section, clean demo slot, login/book demo
- Searchable Bills Database
- Searchable Laws Database
- User Bills dashboard
- Agentic Chatbot workspace
- Upload / extract / metadata / similar-bills / conflict / stakeholder / editing flows
- The homepage and app structure must reflect the screenshots and product notes

==================================================
1. SOURCE-OF-TRUTH REPO INTEGRATION
==================================================

You will be given ClauseAI, ClauseAI-Navilan, and ClauseAI-Shrey.
You must intelligently merge and reuse logic from them.

Follow this source-of-truth mapping:

A. Frontend / UX / flow inspiration
- ClauseAI
- ClauseAI-Navilan
- ClauseAI-Shrey
- plus the screenshots and notes in this prompt as the final product truth

B. Extract Bill / Generate Metadata / Similar Bills
- primarily from ClauseAI-Navilan and ClauseAI-Shrey
- with inspiration from ClauseAI where useful

C. Legal Conflict Analysis
- primarily from ClauseAI-Navilan
- with inspiration from ClauseAI

D. Stakeholder Analysis
- primarily from ClauseAI-Navilan
- with inspiration from ClauseAI

E. Human + agent editing loop
- combine best patterns across all repos, but make it cleaner, more stateful, more elite, and more production-ready

Do not copy messy patterns blindly.
Refactor aggressively where needed.
Unify architecture.
Remove dead code and duplicated logic.
Preserve working logic while improving the system.

==================================================
2. DESIGN / UI / UX REQUIREMENTS
==================================================

The UI must feel elite, intentional, sparse, and calm.
No UI goyslop.
No clutter.
No random gradients or over-designed enterprise junk.
No bloated dashboards.
No cheap card spam.

The screenshots define the vibe:
- black / white minimal aesthetic
- clean framed panels
- strong spacing and hierarchy
- mono / restrained typography is acceptable if done tastefully
- highly legible
- deliberate motion only where useful
- clean transitions between pipeline stages
- strong information density without visual mess
- every analysis page should feel like a serious drafting workstation, not a chatbot toy

Core UI surfaces to build:

1. Homepage
- hero headline
- supporting copy
- demo video or interactive demo block
- login and book demo actions
- clean framed layout matching screenshot intent

2. Auth
- sign in
- sign up
- clean centered auth views matching screenshot direction

3. Main App Shell
- persistent left sidebar
- items:
  - Your Bills
  - Bills Database
  - Laws Database
  - Agentic Chatbot
  - Settings / account controls
- preserve state between navigation
- avoid layout jumps

4. Your Bills page
- grid/list of bills
- create new / upload new
- show recent draft / progress state
- resume in-progress workflows

5. Bills Database page
- search bar
- structured filters
- status filters like passed / failed / expired when available
- clean bill cards / rows
- open detail pane / page
- searchable and actually useful, not decorative

6. Laws Database page
- search bar
- state / jurisdiction filters if relevant
- detail view for law text / summary / references
- clean exploration experience

7. Upload / Extraction flow
- upload bill file: DOCX, PDF, TXT
- extracting text state
- extracted text preview
- metadata generation step
- editable metadata cards/fields
- “find similar bills” action

8. Similar Bills analysis flow
- processing view
- list of matched bills with score / summary / metadata
- click into any bill for detail
- dedicated “similar bills analysis” report
- report must be structured, clean markdown rendered beautifully
- include concise overview + specific suggested fixes
- fixes do not auto-apply silently; they are surfaced as suggestions

9. Legal Conflict analysis flow
- show process / loading state
- structured report
- exact laws / clauses / sections flagged
- rationale
- suggested changes
- clear traceability from law → issue → suggestion

10. Stakeholder analysis flow
- identify likely supporters/opponents/affected groups
- show research / reasoning in clean structured format
- stakeholder cards / expandable views
- show why a stakeholder might oppose and what language changes could reduce opposition
- keep it serious and product-like

11. Human + Agent editing workspace
- central draft editor
- side panel(s) or tabbed analyses
- version history
- backtracking
- accept / reject / modify suggested changes
- allow user manual edits
- agent can propose next edits based on accumulated analyses
- preserve all versions
- downloading/exporting available
- when AI finishes a pass, show clear state and let user continue editing

12. Responsive behavior
- when shrunk, app should still feel intentionally designed
- panels should stack or compress gracefully
- sidebar behavior should be clean
- no broken layouts

Use references from 21st.dev where helpful for UI implementation patterns, but do not cargo-cult flashy components. The end result must match ClauseAI’s restrained vibe.

==================================================
3. 21ST SDK / 21ST AGENTS REQUIREMENT
==================================================

If using 21st.dev references or packages:
1. Fetch https://21st.dev/agents/llms.txt first
2. Treat llms.txt as the primary entry to current docs
3. For docs URLs, always use markdown versions by inserting /md/ in the path
4. Only read the sections actually needed
5. Use 21st references to accelerate clean UI implementation, not to replace product judgment

==================================================
4. BACKEND ARCHITECTURE REQUIREMENTS
==================================================

First, fully scaffold the backend before polishing the UI.

You must design the backend as an agentic workflow system with durable state.

Core requirements:
- codex-like agent loop / tool loop architecture
- deterministic orchestration where needed
- resumable multi-step jobs
- persistent storage of each stage
- ability to stop/resume safely
- versioned artifacts
- separation of user data vs large legislative/reference data
- clean service boundaries

Use PostgreSQL.

Create two databases or clearly separated schemas:

A. App/User database
Contains:
- users
- auth mappings
- organizations / workspaces if needed
- uploaded files
- extracted texts
- metadata records
- workflow runs
- workflow step state
- reports
- suggested edits
- accepted/rejected edits
- draft versions
- chat threads
- events / audit logs
- bookmarks / saved searches / user preferences if useful

B. Legislative / analysis data database
Contains only what is needed for:
- searchable bills
- searchable laws
- bill metadata
- jurisdictions / states
- statuses
- bill text / normalized sections
- law text / normalized sections
- embeddings / search artifacts if used
- linkage tables for similarity/conflict/stakeholder research support
- any required indexes/materialized search structures

OpenStates is already running.
Create a new clean fresh database that contains only what ClauseAI actually needs.
Do not leave the system dependent on a giant messy monolith if a cleaner derived database is better.
Build import / normalization scripts if necessary.

==================================================
5. WORKFLOW / PIPELINE ORCHESTRATION
==================================================

Implement the pipeline as durable jobs with explicit states.

The canonical workflow:

A. Bill Upload / Intake
- user uploads file
- create bill record
- create workflow run
- persist original file and metadata
- enqueue extraction step

B. Extract Bill
- parse DOCX / PDF / TXT robustly
- extract text
- preserve extraction diagnostics
- persist extracted text
- create preview artifact
- allow retry if extraction fails

C. Generate Metadata
Generate structured metadata such as:
- title
- jurisdiction / state
- bill type / code if inferable
- year / session if inferable
- policy topic(s)
- summary
- key sections / clauses
- status if known
- confidence scores
- editable fields
User can review/edit metadata before continuing.

D. Similar Bills Search + Analysis
- find semantically / structurally similar bills
- combine metadata filtering + text retrieval + embeddings + keyword methods as needed
- return ranked results
- store all retrieved candidates
- generate a report:
  - overall assessment of the user’s bill
  - what is working
  - what needs improvement
  - 1-2 basic fixes (grammar, section clarity, structure, formatting, etc.)
  - 3-4 substantive language adaptation suggestions from similar bills
  - every substantive suggestion must cite which bill / section inspired it and why
  - suggestions are recommendations, not silent edits
- generate machine-readable edit suggestion objects in parallel with human-readable report

E. Legal Conflict Search + Analysis
- find potentially conflicting existing laws / statutes / clauses
- analyze legal overlap, contradiction, preemption risk, implementation conflicts, drafting ambiguity
- generate report:
  - overall legal risk summary
  - specific conflicting laws / clauses
  - explanation of risk
  - suggested language changes
  - traceability from source law to recommendation
- also produce machine-readable edit suggestions

F. Stakeholder Opposition Search + Analysis
- identify stakeholders likely to oppose or be affected
- include categories like trade groups, labor, agencies, advocacy groups, industry actors, public-interest orgs, etc. where relevant
- determine concerns and probable opposition vectors
- generate report:
  - overall stakeholder risk summary
  - stakeholders grouped by type / priority
  - reasons for likely opposition
  - suggested language shifts or carveouts that reduce opposition while preserving bill intent
- also produce machine-readable edit suggestions

G. Human + Agent Editing
- aggregate suggestions from similar-bills, legal, and stakeholder phases
- preserve provenance of each suggestion
- surface them in the editing workspace
- let agent propose an ordered editing plan
- user can accept, reject, or modify edits
- preserve every revision as a version
- allow backtracking and comparison
- allow additional agent loops over current draft

==================================================
6. PERSISTENCE / STATE / RECOVERY
==================================================

This is mandatory.

The system must save every step.
If the user:
- refreshes
- quits
- closes tab
- navigates away
- backtracks
- returns later
- reopens another device
the system should resume correctly.

Persist:
- uploaded file
- extracted text
- metadata
- similar bill candidates
- conflict candidates
- stakeholder candidates
- all reports
- all structured suggestion objects
- workflow step statuses
- intermediate job outputs
- draft versions
- accepted / rejected decisions
- UI thread / agent conversation state where relevant
- timestamps / run ids / audit trail

Need idempotent jobs.
Need resumable steps.
Need explicit state machine or equivalent.
Need optimistic but safe frontend updates.

==================================================
7. AGENT SYSTEM REQUIREMENTS
==================================================

This is not one dumb prompt.
Design a clean multi-agent or multi-stage prompting system with durable orchestration.

Recommended agent roles:

1. Intake / Extraction Agent
- normalizes uploaded input
- validates extraction quality
- prepares structured intake payload

2. Metadata Agent
- infers metadata fields
- produces editable structured metadata with confidence

3. Similar Bills Retrieval Agent
- query generation
- search expansion
- ranking / deduplication

4. Similar Bills Analysis Agent
- reads user bill + matched bills
- produces report + structured edit suggestions

5. Legal Conflict Retrieval Agent
- identifies relevant existing laws / statutes / clauses
- performs scoped retrieval

6. Legal Conflict Analysis Agent
- explains conflict risk and proposes fixes

7. Stakeholder Retrieval Agent
- identifies affected stakeholder groups, institutions, and opposition vectors

8. Stakeholder Analysis Agent
- explains opposition and proposes language changes

9. Editing Strategist Agent
- merges suggestions into an ordered revision plan
- avoids contradictory edits
- asks for user approval where needed

10. Collaborative Drafting Agent
- operates in the editing UI
- proposes diffs, rewrites, alternatives, explanations
- never destroys version history
- always acts on the currently selected draft version

The orchestration layer must:
- pass structured outputs between agents
- validate schemas
- preserve provenance
- store artifacts at each stage
- allow retries without corrupting downstream state

==================================================
8. PROMPTING QUALITY REQUIREMENTS
==================================================

All prompts for all agents must be elite, specific, and grounded.
Do not use vague generic prompts.

Prompting principles:
- define exact role
- define exact input schema
- define exact output schema
- define constraints
- distinguish analysis from editing
- require traceability
- require evidence-based recommendations
- require separation of “basic drafting fixes” vs “substantive language adaptations”
- require preservation of legislative intent
- require clear explanation of why a change helps
- require machine-readable outputs for downstream use

Each major analysis agent should produce both:
1. human-readable markdown report
2. structured JSON artifact

The human-readable report should be beautiful and clean in markdown.
The structured output should include things like:
- issue id
- category
- severity / priority
- title
- explanation
- evidence / references
- recommended change
- suggested patch or replacement text if available
- provenance
- confidence
- related source ids

==================================================
9. EDITING MODEL REQUIREMENTS
==================================================

Important product philosophy:
The system is analysis-first, collaborative-editing-second.

That means:
- during the pipeline phases, generate reports and suggestions
- do not silently overwrite the draft without preserving provenance
- when edits are proposed, store them as suggestions
- once in the editing workspace, let user review and control changes

The editing workspace must support:
- draft text view
- change suggestions grouped by source:
  - similar bills
  - legal conflicts
  - stakeholder concerns
- click a suggestion to expand into full analysis
- apply suggestion
- reject suggestion
- partially adapt suggestion
- compare current draft to prior versions
- show version graph or linear history
- restore older versions
- continue agent-assisted drafting from any prior version

Need robust internal draft format.
Need stable diffing.
Need human-readable version labels.

==================================================
10. DATABASE / SEARCH REQUIREMENTS
==================================================

Implement real search for:
- bills database
- laws database

Need:
- text search
- metadata filtering
- clean indexing
- performant pagination
- detail views

For similar bill retrieval, use a hybrid approach if useful:
- metadata filters
- text search
- embeddings
- section-aware matching
- reranking

For legal conflict search:
- law section normalization
- statute text indexing
- conflict candidate retrieval that can be justified

For stakeholder analysis:
- use available data sources / repo logic / retrieval patterns to infer likely stakeholders
- if external search is needed in architecture, scaffold it cleanly, but do not make fake claims

==================================================
11. CODEBASE QUALITY REQUIREMENTS
==================================================

You are not just shipping features.
You are creating a foundation.

Requirements:
- clean monorepo or clearly structured app
- strong typing
- modular backend services
- explicit schemas
- clean database migrations
- background job architecture where needed
- observable logs
- error handling
- retries
- testable service boundaries
- seed scripts / import scripts where needed
- documented environment variables
- clean README and run instructions
- no dead scaffolding
- no mystery magic
- no spaghetti callbacks

If the existing repos are messy:
- preserve working business logic
- refactor into sane modules
- clearly mark migrated logic
- avoid unnecessary rewrites when a precise extraction/refactor will do

==================================================
12. FRONTEND IMPLEMENTATION REQUIREMENTS
==================================================

The frontend should feel extremely polished.

Use:
- clean panel framing
- minimal palette
- strong whitespace
- smooth interactions
- thoughtful loading states
- subtle progress surfaces
- beautiful markdown rendering
- excellent empty states
- restrained icons
- no visual noise

Critical views:
- homepage
- auth
- app shell
- your bills
- bills database
- laws database
- upload flow
- extraction flow
- metadata review
- similar bills processing/results/report
- legal conflict processing/results/report
- stakeholder processing/results/report
- collaborative editing workspace
- version history
- suggestion detail drawers/panels

The analysis reports should render in a very clean markdown style.
The user should be able to see a truncated preview, then click into a full detailed clean page/panel.

==================================================
13. USER EXPERIENCE DETAILS THAT MUST EXIST
==================================================

Must support:
- save drafts automatically
- resume unfinished analysis
- clear progress indicator across pipeline stages
- visible processing states
- expandable candidate bill / law / stakeholder detail
- click-through from suggestion to source evidence
- editable generated metadata before continuing
- ability to revisit earlier steps without data loss
- download/export current draft
- ability to continue editing after an AI pass completes
- durable user session continuity

==================================================
14. WHAT TO DELIVER
==================================================

Deliver the implementation as if preparing a serious internal handoff.

Need:
1. Final architecture
2. Folder structure
3. Backend scaffold
4. Database design
5. Workflow/state model
6. Agent prompt set
7. Key UI screens
8. Integration of useful logic from ClauseAI / ClauseAI-Navilan / ClauseAI-Shrey
9. Migrations / schema
10. Seed/import pipeline for clean legislative db
11. Minimal but real tests for critical paths
12. README with setup and run
13. Clear comments only where useful
14. No fake placeholders unless explicitly marked
15. If something cannot be completed, leave a precise TODO with rationale

==================================================
15. OUTPUT FORMAT FOR YOUR WORK
==================================================

Proceed in this order:

Phase 1: Audit
- inspect the provided repos
- identify reusable logic by area
- identify gaps, duplication, and broken abstractions
- propose the merged architecture

Phase 2: Scaffolding
- implement database schemas
- workflow engine/state model
- services
- retrieval modules
- analysis artifact storage
- versioning model

Phase 3: Agent Prompts
- implement all core system prompts and schemas
- ensure structured outputs
- ensure traceability

Phase 4: Frontend
- implement app shell and key views
- wire real state and data loading
- match screenshot vibe closely

Phase 5: Integration
- connect frontend to backend pipeline
- ensure persistence and resumability
- test full flow

Phase 6: Polish
- improve loading states
- improve markdown rendering
- improve edit suggestion UX
- eliminate rough edges
- tighten visual language

For each phase, make real progress in code, not just prose.

==================================================
16. HARD CONSTRAINTS
==================================================

- Do not make the UI generic.
- Do not build a chatbot-only product.
- Do not skip persistence.
- Do not silently mutate bills without traceability.
- Do not collapse all logic into one giant prompt.
- Do not leave workflow state implicit.
- Do not make fake database search.
- Do not ignore the screenshots.
- Do not ignore the repo split guidance.
- Do not over-engineer with unnecessary infra if a simpler strong design works.
- Do not delete provenance of suggestions or versions.

==================================================
17. SUCCESS CRITERIA
==================================================

The build is successful if:

- a user can upload a bill
- text is extracted and saved
- metadata is generated and editable
- similar bills are found and analyzed
- legal conflicts are found and analyzed
- stakeholder opposition is found and analyzed
- all suggestions are persisted as structured artifacts
- user enters a clean collaborative editing UI
- user can review/apply/reject suggestions
- version history works
- refresh/resume works
- bills database and laws database are searchable from the app
- homepage and app match the screenshot vibe
- codebase is coherent and production-leaning
- prompts are strong and domain-specific
- the system feels elite

Now begin by auditing the provided codebases and assets, then build the merged production scaffold and implementation.

First thing the user sees:
That clean loginpage from the screenshots
Once log in, they a side bar nav with (Your Bills, Bills Database, Laws Database, Agentic Chatbot, Settings, Log out (Sign in if they haven't already)) also in the screenshots
Your bills
If a new bill (+ sign)
Page 1: Upload your bill page Extracting text with loading animation, once done
Page 2: Then shows extracted text, they can edit it, then a generated metadata button
Page 3: Then generates metadata, with Codex 5.1 Mini, which also is editable with a find similar bills
Page 4: Then it finds similar bills page, reads out the similar bills (Detailed info in the screenshots), with a Similar Bills Analysis button
Page 5: MD Report + Fixes cleanly, then onto Legal Conflict page
Page 6: Finds legal conflicts, does MD Report + fixes check details in screenshots 
Page 7: Finds stakeholder opposition with web search, does MD Report + fixes check details in screenshots
Page 8: Now the Agentic UI with the editable document, the codex like chatbot UI on the right, see screenshots for details
Page 9: Once done, we are good
If it is an old bill (They can just navigate through, and can also edit and redo stuff)
The your bills page they can also delete bills, and make sure there is good version history stuff across the stuff 

For Agentic chatbot, just like make it so the user, can ask questions about their bills, web search, edit stuff, and the database, look at the screenshots

For the bills and laws database, look at the screenshots, but they should be able to cleanly search through and look at stuff, filter by things, and more