# App Shell And Auth

## Required Pages

- Homepage
- Login
- Sign up
- Your Bills
- Bills Database
- Laws Database
- Agentic Chatbot
- Settings

## Homepage

Reference intent from screenshots:

- minimal framed shell
- strong headline
- restrained supporting copy
- login and book-demo actions
- one central demo block

Planned behavior:

- left-aligned product statement
- right-aligned top nav actions
- embedded product demo panel
- no noisy marketing sections above the fold
- below-fold sections only if they help conversion and product understanding

Inspiration to borrow carefully:

- Fed10-level editorial sharpness
- 21st-quality component finish

## Auth

Requirement:

- email + password
- no verification

Screens imply:

- centered form
- dark restrained frame
- very simple action hierarchy

Planned flows:

- sign up
- sign in
- sign out
- optional password reset later, not required for initial scaffold

## Main App Shell

Persistent left navigation:

- Your Bills
- Bills Database
- Laws Database
- Agentic Chatbot
- Settings

Shell rules:

- no route should feel like a brand-new app
- nav width must collapse cleanly on smaller widths
- current project context remains visible
- state restoration on refresh must return the user to the last meaningful surface

## Your Bills

Purpose:

- landing zone after login
- resume in-progress workflows
- create a new bill workspace

Required elements:

- create/upload new bill
- recent projects
- stage/status badge
- updated timestamp
- quick resume action

## Bills Database

Purpose:

- search historical bills
- feed similar-bill analysis
- allow manual exploration

Required elements:

- strong search input
- filters for jurisdiction, year/session, status, topic
- row/card results with status and preview
- detail drawer or detail page

## Laws Database

Purpose:

- search California and U.S. laws
- inspect exact sections the AI cites

Required elements:

- keyword and citation search
- jurisdiction/source filters
- law detail view with hierarchy path
- exact section text
- source URL

## Agentic Chatbot

Purpose:

- research workspace outside the strict pipeline
- persistent thread history per project or global workspace

Required elements:

- chat transcript
- tool/action history
- references to bills/laws where relevant
- ability to pull project context into a thread

## UX Requirements Across The Shell

- black-first restrained palette
- clear framed panels
- mono-forward or utilitarian typography for operational surfaces
- no dashboard-card spam
- every page has one obvious next action
- loading states should feel deliberate, not generic
