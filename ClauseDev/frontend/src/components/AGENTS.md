# Components Guide

## Role
- Reusable UI scaffolding only.
- Keep these components presentation-focused unless there is a strong shared interaction need.

## Preferred Content
- Layout shells
- Section frames
- Reusable navigation elements
- Small stable display primitives
- Explicit next/previous page affordances
- Status and empty-state primitives

## Avoid
- Page-specific workflow logic
- Direct API access from generic components
- Hidden assumptions about a single route unless the component is intentionally route-bound
- Ambiguous buttons like `Continue` when the component can say the exact next page
