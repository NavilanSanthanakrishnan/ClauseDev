# Workflow And Editor

## End-To-End Workflow

1. Upload bill
2. Extract text
3. Generate metadata
4. Find similar bills
5. Analyze similar bills
6. Find conflicting laws
7. Analyze conflicts
8. Find stakeholder opposition
9. Analyze stakeholder opposition
10. Enter collaborative editing workspace
11. Export final draft and changelog

## Step 1: Upload / Extract

Requirements from screenshots and prompt:

- support `docx`, `pdf`, `txt`
- obvious upload target
- extraction progress state
- extracted-text preview
- no hidden transition into later steps

Stored artifacts:

- original file
- extracted text
- extraction warnings
- parser metadata

## Step 2: Metadata

Editable fields:

- title
- summary
- jurisdiction
- policy area
- affected entities
- keywords/tags

Rules:

- generated metadata is editable before retrieval starts
- user can rerun metadata without losing draft context

## Step 3: Similar Bills Search

UI shape from screenshots:

- processing/list panel
- clickable similar-bill cards
- right-side detail surface for selected bill
- dedicated “Similar Bills Analysis” action

Expected result content:

- score
- title and identifier
- jurisdiction and year/session
- passed/failed/expired status
- short analysis summary
- ability to open full text or source URL

## Step 4: Similar Bills Report + Fixes

Report page:

- short clean markdown report
- overview first
- concise findings
- visible next action

Fixes page:

- discrete fix cards
- each fix has traceability
- fix explains which comparison bill influenced it and why
- nothing auto-applies on the report page

## Step 5: Legal Conflict Analysis

Output requirements:

- exact law citations
- exact conflicting bill sections when possible
- risk level
- reasoning
- suggested fixes

Surface requirements:

- loading/progress state
- report page
- fixes page

## Step 6: Stakeholder Analysis

Output requirements:

- likely supporters/opponents
- reasons for support/opposition
- web research trace
- language changes that reduce opposition without losing core policy intent

Surface requirements:

- entity list/cards
- clean rationale display
- report page plus fixes page

## Step 7: Collaborative Drafting Workspace

This is the highest-value surface in the product.

Hard requirements from screenshots and prompt:

- central editable draft
- analysis tabs or side panels
- visible version history
- backtracking
- user accepts/rejects/modifies suggestions
- agent continues suggesting changes using accumulated context
- user can edit manually at any time
- export available at any time

Planned workspace layout:

- left rail for analysis/fix tabs and version timeline
- center draft editor
- right rail for agent/chat and focused suggestion details

## Suggestion Lifecycle

1. AI creates suggestion
2. suggestion is stored with source references
3. user opens suggestion
4. user accepts, rejects, or modifies
5. resulting draft version is persisted
6. change log updates

## Version History Rules

- every AI-applied change creates a new draft version
- every significant manual edit checkpoint can create a version
- user can restore prior versions without corrupting suggestion history
- applied suggestions remain attributable even after later edits

## Final Export

Formats:

- `.docx`
- `.pdf`
- `.txt`

Export metadata:

- current draft
- optional redline/change log
- summary of accepted/rejected suggestions
