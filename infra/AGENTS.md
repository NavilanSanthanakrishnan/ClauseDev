# Infra Guide

## Role
- Database bootstrap SQL
- Shell scripts for provisioning and data materialization

## Critical Constraint
- `clauseai-db` must include all relevant OpenStates bill rows plus the curated legal corpora.
- Trimming is allowed for columns and redundant tables, not for dropping the bill corpus scope.

## Editing Rules
- Be explicit about which source tables feed each product table.
- Prefer idempotent-ish setup where practical.
- Keep bootstrap scripts honest about runtime; large materializations are expected.
