# Delivery Phases

## Execution Order

Backend and data first.

The frontend should not outrun the actual workflow and persistence model.

## Phase 0: Repo And Planning

Deliverables:

- GitHub repo
- planning package

Status:

- complete in this turn

## Phase 1: Repo Scaffold And Local Tooling

Deliverables:

- backend scaffold
- frontend scaffold
- electron scaffold
- migration setup
- lint/test tooling

Test gate:

- backend boots
- frontend boots
- Electron dev shell boots

## Phase 2: Databases

Deliverables:

- create `"clauseai-db"`
- create `"clauseai-db-user"`
- add migrations
- implement DB connection layer

Test gate:

- migrations run cleanly
- both DBs connect in app and tests

## Phase 3: Reference Data Ingestion

Deliverables:

- OpenStates flatten/import
- California official code import
- U.S. Code import
- canonical legal index build

Test gate:

- search smoke tests pass
- bill and law detail queries return expected fields

## Phase 4: Auth + Core App Persistence

Deliverables:

- signup/login/logout/refresh
- projects
- source docs
- draft versions
- workflow tables

Test gate:

- full auth cycle works
- project creation and restore works

## Phase 5: Pipeline Stages

Deliverables:

- upload/extract
- metadata
- similar bills search
- similar bills report/fixes
- legal report/fixes
- stakeholder report/fixes

Test gate:

- each stage passes in isolation
- combined workflow passes end-to-end

## Phase 6: Collaborative Editor

Deliverables:

- suggestion application
- manual editing
- version history
- backtracking
- export

Test gate:

- accept/reject/modify flows pass
- prior versions restore correctly

## Phase 7: UI Polish And Electron Packaging

Deliverables:

- final visual system
- responsive hardening
- desktop packaging

Test gate:

- web build passes
- `.dmg` build passes
- `.exe` build passes

## Commit Cadence

Commit and push after every meaningful completed slice.

Minimum expected cadence:

- scaffold
- DB setup
- each ingestion source
- auth
- each major workflow stage
- editor
- packaging
- major prompt updates

## Working Rule

At each phase:

1. implement
2. test from user perspective
3. test from code perspective
4. fix failures
5. retest
6. commit
7. push

## Stop/Ask Rule

If implementation uncovers ambiguous product behavior that materially changes:

- the database model
- the editor semantics
- the legal analysis scope
- the packaging strategy

stop and ask for approval instead of forcing a risky assumption.
