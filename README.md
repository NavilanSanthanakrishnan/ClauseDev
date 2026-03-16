# Clause

Clause is the parent application repository.

Right now it contains:

- `Step1/`: the first working bill-similarity retrieval system

Step1 is the current completed slice:

- upload a bill
- extract the text
- profile it with Codex OAuth `gpt-5.4`
- retrieve similar bills from OpenStates
- rerank them semantically
- return the strongest matches in a simple HTML UI

Repository structure:

- `Step1/README.md`: Step1 setup, run instructions, and architecture
- `Step1/FUTURE.md`: roadmap for pushing search quality and latency much further

Next direction:

- use Step1 as the retrieval/search foundation
- build the broader Clause application around it
- use the existing ClauseAI codebase as the reference for the larger workflow, UX, and report-generation path
