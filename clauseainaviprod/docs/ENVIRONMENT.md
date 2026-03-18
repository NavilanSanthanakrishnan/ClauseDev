# Environment

`Clause` reads runtime configuration from an external file:

`/Users/navilan/Documents/ClauseAIProd/.env.clauseainaviprod`

That keeps secrets outside the project folders and outside Git.

## Required later for Gemini-powered agentic search

```bash
CLAUSE_GEMINI_API_KEY=your_key_here
CLAUSE_GEMINI_MODEL=gemini-2.5-flash
CLAUSE_GEMINI_EMBEDDING_MODEL=gemini-embedding-001
```

## Optional

```bash
CLAUSE_DATABASE_PATH=/absolute/path/to/clause.sqlite3
CLAUSE_DEBUG=true
```

## When to add keys

Add the Gemini keys after:
1. the backend and frontend are fully wired
2. the seed database or imported dataset is ready
3. the embedding build script is ready to run

That way testing covers the full retrieval loop instead of only the planner call.

