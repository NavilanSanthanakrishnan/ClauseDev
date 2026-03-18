# Infra SQL Guide

## Main File
- `reference_db.sql` is the canonical reference corpus materialization script.

## What It Must Do
- Materialize `bill.*` product tables from OpenStates
- Materialize `law.*` product tables from California code, legal index, and U.S. Code
- Create the search-facing views used by the app

## Guardrails
- Keep all OpenStates bill rows in scope.
- Remove only columns/tables that are not useful to the application.
- Watch for FDW duplicates when joining version/source link tables.
- Index only what the app genuinely queries, but ensure text search remains usable.
