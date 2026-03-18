# Frontend And Electron Plan

## Stack

- React
- Vite
- React Router
- TanStack Query for server state
- Monaco or CodeMirror for draft editing
- Electron for desktop packaging
- Playwright for UI and e2e tests

## Design Direction

Source requirements:

- screenshot-driven black minimal shell
- no generic SaaS gradients
- no default Tailwind look
- operational, calm, intentional

Planned visual language:

- dark charcoal background
- off-white type and frames
- sparse, precise accent color for state and actions
- high-density panels without visual clutter

Typography direction:

- operational mono for labels/data
- more expressive serif or editorial face for hero statements only

## Route Map

- `/`
- `/login`
- `/signup`
- `/bills`
- `/bills/database`
- `/laws/database`
- `/chat`
- `/projects/:projectId/upload`
- `/projects/:projectId/extraction`
- `/projects/:projectId/metadata`
- `/projects/:projectId/similar-bills`
- `/projects/:projectId/similar-bills/report`
- `/projects/:projectId/similar-bills/fixes`
- `/projects/:projectId/legal/report`
- `/projects/:projectId/legal/fixes`
- `/projects/:projectId/stakeholders/report`
- `/projects/:projectId/stakeholders/fixes`
- `/projects/:projectId/editor`

## Screen Planning

### Homepage

- hero copy
- demo block
- login and book-demo CTA
- no bloated marketing clutter

### App shell

- persistent left rail
- project-aware top bar
- content area with stable framing

### Bills and laws databases

- keyboard-friendly search
- detail panel on selection
- filters that stay visible without taking over the page

### Report pages

- markdown rendered beautifully
- summary first
- exact next action at bottom

### Fix pages

- stack of discrete fixes
- click into detail without losing context

### Editor

- center drafting surface
- lateral analysis context
- agent panel
- version rail

## Electron Plan

Electron lives in a dedicated top-level `electron/` folder, not mixed into the frontend runtime code.

Responsibilities:

- native window shell
- secure preload bridge
- filesystem export helpers
- update and packaging hooks

Packaging targets:

- web build
- macOS `.dmg`
- Windows `.exe`

## Desktop/Web Parity Rule

The app must work as a web product first.

Electron adds:

- native packaging
- local file affordances
- better OS integration

Electron must not become a separate fork of the UI.

## Inspiration Notes

From `fed10.ai`:

- serious product storytelling
- dense “intelligence surface” layouts
- strong preview panels on landing surfaces

From `21st.dev`:

- polished component craft
- intentional interaction details
- modern motion patterns used sparingly

## Frontend Definition Of Done

- all required surfaces exist
- responsive behavior is intentional
- route-to-route state restoration works
- analysis and editor surfaces feel like one system
- web, macOS, and Windows builds are reproducible
