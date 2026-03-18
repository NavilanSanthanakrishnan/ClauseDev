# Prompts And Evals

## Prompt Strategy

The product depends on prompts being modular, testable, and stage-specific.

We should not bury prompts inside service code.

## Prompt Sources To Rework

- current `prompts/prompt.md`
- current `prompts/workflow.md`
- current backend prompts from `repos/ClauseAI/backend/data/prompts`
- logic and wording patterns from Navilan/Shrey stage services

## Planned Prompt Inventory

- extraction cleanup prompt
- metadata generation prompt
- bill profile prompt
- similar-bills comparative analysis prompt
- similar-bills fix generation prompt
- legal conflict report prompt
- legal conflict fix prompt
- stakeholder analysis report prompt
- stakeholder fix prompt
- editor agent prompt
- export summary prompt

## Prompt Structure

Every production prompt should have:

- `system.md` or `.txt`
- `user.md` or `.txt`
- JSON schema for output
- fixture inputs
- expected high-level behaviors

## Output Discipline

Prefer structured JSON for machine-consumed outputs:

- metadata fields
- similar bill candidates
- section-level fix proposals
- conflict objects
- stakeholder objects
- editor suggestions

Markdown should be used for:

- human-readable reports
- rationale text
- export summaries

## Eval Harness

We need a prompt-eval harness before implementation spreads.

Eval categories:

- schema validity
- citation coverage
- suggestion specificity
- hallucination resistance
- edit traceability
- report readability

## Golden Test Cases

Seed cases should include:

- California EV charging bill
- wage/hour conflict synthetic case
- minimum wage conflict synthetic case
- housing bill with stakeholder tension
- healthcare bill with similar-bill precedent

## Acceptance Standard Per Stage

### Similar-bills analysis

- cites actual comparison bills
- does not invent bill outcomes
- suggestions reference concrete structural patterns

### Legal conflict analysis

- cites exact statutes
- distinguishes real conflicts from vague risk
- identifies direct amendment context where present

### Stakeholder analysis

- ties claims to specific stakeholder logic or retrieved evidence
- suggestions reduce opposition in a measurable way

### Editor agent

- never silently mutates the draft without creating a suggestion or a version

## Iteration Loop

1. write prompt
2. run fixture set
3. inspect failures
4. tighten prompt and validator
5. rerun
6. lock prompt version

## Prompt Versioning

- every prompt change should be committed
- prompt versions should be attributable to report differences
- major prompt edits should trigger focused regression runs
