# Design System

## Intent
`Clause` should read like a serious drafting desk: restrained, clear, and deliberate.

## Visual rules
- Dark editorial canvas
- Serif display type for key headings only
- Sans body type everywhere else
- Large radii, soft borders, and low-contrast surfaces
- White actions reserved for the highest-priority button on a surface

## Type
- Display: `Iowan Old Style`, then Palatino fallbacks
- Body: `Avenir Next`, then `Segoe UI`
- Use serif only for:
  - product lockup
  - page titles
  - major section titles

## Color
- Background: `#0a0a0a`
- Elevated surface: `rgba(18, 18, 18, 0.92)`
- Border: `rgba(255, 255, 255, 0.08)`
- Primary text: `#f4f1ea`
- Secondary text: `rgba(244, 241, 234, 0.62)`
- Primary action: `#f4f1ea` with dark text
- Error: low-saturation red, never bright red

## Layout
- Three-column desktop shell:
  - left nav
  - main work area
  - right intelligence rail
- Collapse to single-column on smaller screens without changing information hierarchy.
- Every page should answer:
  - where am I
  - what can I do here
  - what is selected

## Product behavior
- Search modes should be explicit and labeled in plain language.
- The workspace rail should summarize, not overwhelm.
- Editing actions should be obvious:
  - refresh analysis
  - save draft
  - run agent

## Anti-patterns
- No flashy gradients or bright accent colors
- No toy-like badges, counters, or celebratory motion
- No hidden primary workflow behind multiple tabs
