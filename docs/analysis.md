# Goalkeepr Analysis

## Background

- Youth football score recording for one household team
- Current workflow: phone-based Excel spreadsheet
- Spreadsheet as completed-match history
- Primary user: parent at a match
- Goal: faster, less error-prone score entry
- Small, low-maintenance first release

## Technical Direction

- Django, server-rendered HTML, HTMX
- Async function-based views and async ORM support where applicable
- ASGI application via Uvicorn
- PostgreSQL for durable data
- Procedural, fully type-annotated Python
- mypy type checks, pytest function tests, Ruff formatting and linting
- devenv tooling; Nushell commands and scripts
- Plain HTML, CSS, JavaScript, and locally bundled Pico CSS
- Minimal, mobile-first visual design
- UTC timestamps
- Local Docker Compose: Django application and PostgreSQL
- Docker Compose and Dockerfile structure based on `facturette`
- No Kubernetes, ingress, TLS, image publishing, backups, production secrets, or external services

## Users And Access

- Standard Django authentication and security features
- One shared household account for initial use
- No public registration, account management, or password-reset screens
- Initial account through Django `createsuperuser`
- Public read-only access to the match list and match details
- Authentication required for match creation, editing, deletion, score recording, and undo
- Strict user ownership for matches and score events
- No public write operations

## MVP Scope

- One configured household team
- Team name from the `TEAM_NAME` Django setting
- `TEAM_NAME` loaded with `django-environ`
- Default team name: `K.F.C. Sparta Kolmont`
- No team management
- No season management
- Match creation: date, opponent name, home or away flag, optional location and notes
- Home selected by default for new matches
- Location hidden and unavailable for home matches
- Location visible and optional for away matches
- Submitted location discarded for home matches
- Large score controls for either side
- Timestamped score events
- Most-recent score-event undo for either side
- Derived current and final scores
- Public results browsing in reverse chronological order
- Public click-through from match list to match detail
- Public match detail and score-event history are read-only
- Historical match editing and deletion
- Delete confirmation
- Score entry for every match
- No match-status workflow
- Authentication before data changes

## Score Recording Flow

- Match opened on a phone
- Configured household team and opponent shown in home-away order
- Large goal controls for either side
- Persistent timestamped event per tap
- Immediate undo for accidental taps
- Results immediately available in public match history

## Initial Data Model

- `Match`: direct user ownership; opponent name, date, home or away flag, optional away location and notes
- `ScoreEvent`: match ownership; scoring side, recorded timestamp
- Scores: event counts by side
- Household team name is configuration, not persisted domain data
- Excluded: players, scorers, assists, match minutes, individual statistics
- Excluded: teams and seasons

## Screens

- Login and logout
- Public match list
- Match create and edit form
- Match score-entry screen
- Public read-only match detail and score-event history

## Non-Goals

- Native mobile apps
- JavaScript SPA
- Offline queues and synchronization
- Realtime multi-parent score editing
- Player statistics and scorer tracking
- League tables, standings, fixture imports, calendar synchronization
- Team management
- Season management
- Dedicated public sharing links or access tokens
- Kubernetes and production deployment configuration

## Acceptance Criteria

- Local application startup through Docker Compose
- Configured household team name defaults to `K.F.C. Sparta Kolmont`
- Team name can be overridden through the environment
- Phone-sized match creation and goal recording
- Home is selected for a new match without requiring an extra click
- Location cannot be entered or retained for a home match
- Location can be entered for an away match
- Displayed score equal to persisted score events
- Most-recent accidental goal undo
- Anonymous users can browse all matches and click through to read-only match details
- Anonymous users cannot create, edit, delete, score, or undo matches
- Authenticated users cannot modify another user's matches or score events
- Match results are ordered by date without season grouping

## Required Code Changes

- Remove the `Team` and `Season` models and their forms, views, URLs, templates, admin registrations, and tests
- Add direct user ownership to `Match`
- Add a data migration that copies each existing match owner from its season's team before removing team and season records
- Preserve existing matches and score events during the migration
- Replace season-scoped match creation with direct authenticated match creation
- Replace team and season navigation with match-focused navigation
- Make match list and match detail views public and read-only
- Keep score entry, goal creation, undo, editing, and deletion authenticated and owner-scoped
- Load `TEAM_NAME` with `django-environ` and expose it to templates
- Render the configured team name on the correct home or away side
- Default new match forms to home
- Conditionally show the location field only when away is selected
- Clear location during server-side validation when home is selected
- Explicitly select Pico's light color scheme to prevent unreadable light text on light backgrounds
- Remove Python properties from application models
- Calculate scores with explicit ORM annotations or view context values
- Prefer namespaced imports, such as `import tracker.models` with `tracker.models.Match`
- Keep `django-stubs` enabled with the Django mypy plugin
- Keep strict mypy checks enforced in project configuration and verification
- Add focused tests for public access, write protection, ownership, team-name rendering, home defaults, away location, and home location clearing
