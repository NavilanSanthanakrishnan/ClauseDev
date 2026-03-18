# Clause

Clause is the parent application repository.

Right now it contains:

- `Step1/`: the current working retrieval plus editing workflow slice

Step1 now covers:

- upload a bill
- extract the text into a workflow session
- generate editable bill metadata with Codex OAuth `gpt-5.4`
- retrieve similar bills from OpenStates with live progress updates
- rerank them semantically
- create a persistent workflow session for the uploaded draft
- stage the draft plus structured retrieval context into a per-session workspace
- run a real local `codex app-server` thread against that workspace
- stream the live Codex loop into the browser
- gate every draft file change behind visible approve or reject controls
- move from Step 3 cleanup into Step 4 strengthening inside one continuous Codex loop
- move from Step 4 into Step 5 stakeholder investigation with web search inside that same loop
- write a structured stakeholder report before proposing Step 5 bill changes
- use the stakeholder report to drive narrow, politically and operationally viable bill edits
- reread the full user bill after every accepted patch before planning the next change

By default, Step1 assumes you already have an `openstates` PostgreSQL database locally. Running the Step1 bootstrap adds the prebuilt retrieval layer inside that same database under the `step1` schema.

If you also have `public.clauseai_bill_table` populated, Step1 will use it to stage richer Step 4 source-bill context, including structured sections when available.

Step1 now assumes the local `codex` CLI is installed and authenticated because the editing workflow is driven through `codex app-server`, not the older one-shot JSON suggestion path.

Repository structure:

- `Step1/README.md`: Step1 setup, run instructions, workflow behavior, and architecture
- `Step1/FUTURE.md`: roadmap for pushing search quality and latency much further

Next direction:

- use Step1 as the retrieval/search foundation
- build the broader Clause application around it
- use the existing ClauseAI codebase as the reference for the larger workflow, UX, and report-generation path
