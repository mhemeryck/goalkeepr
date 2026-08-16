# Goalkeepr Analysis

## Background

- [x] Youth football score recording for one household team
- [x] Current workflow: phone-based Excel spreadsheet
- [x] Spreadsheet as completed-match history
- [x] Primary user: parent at a match
- [x] Goal: faster, less error-prone score entry
- [x] Small, low-maintenance first release

## Technical Direction

- [x] Django, server-rendered HTML, HTMX
- [x] Async function-based views and async ORM support where applicable
- [x] ASGI application via Uvicorn
- [x] PostgreSQL for durable data
- [x] Procedural, fully type-annotated Python
- [x] mypy type checks, pytest function tests, Ruff formatting and linting
- [x] devenv tooling; Nushell commands and scripts
- [x] Plain HTML, CSS, JavaScript, and locally bundled Pico CSS
- [x] Minimal, mobile-first visual design
- [x] UTC timestamps
- [x] Local Docker Compose: Django application and PostgreSQL
- [x] Docker Compose and Dockerfile structure based on `facturette`
- [x] No Kubernetes, ingress, TLS, image publishing, backups, production secrets, or external services

## Users And Access

- [x] Standard Django authentication and security features
- [x] One shared household account for initial use
- [x] No public registration, account management, or password-reset screens
- [x] Initial account through Django `createsuperuser`
- [x] Public read-only access to the match list and match details
- [x] Authentication required for match creation, editing, deletion, score recording, and undo
- [x] Strict user ownership for matches and score events
- [x] No public write operations

## MVP Scope

- [x] One configured household team
- [x] Team name from the `TEAM_NAME` Django setting
- [x] `TEAM_NAME` loaded with `django-environ`
- [x] Default team name: `K.F.C. Sparta Kolmont`
- [x] No team management
- [x] No season management
- [x] Match creation: date, opponent name, home or away flag, and optional notes
- [x] Home selected by default for new matches
- [x] Large score controls for either side
- [x] Timestamped score events
- [x] Most-recent score-event undo for either side
- [x] Derived current and final scores
- [x] Public results browsing in reverse chronological order
- [x] Public click-through from match list to match detail
- [x] Public match detail and score-event history are read-only
- [x] Historical match editing and deletion
- [x] Delete confirmation
- [x] Score entry for every match
- [x] No match-status workflow
- [x] Authentication before data changes

## Score Recording Flow

- [x] Match opened on a phone
- [x] Configured household team and opponent shown in home-away order
- [x] Large goal controls for either side
- [x] Persistent timestamped event per tap
- [x] Immediate undo for accidental taps
- [x] Results immediately available in public match history

## Initial Data Model

- [x] `Match`: direct user ownership; opponent name, date, home or away flag, and optional notes
- [x] `ScoreEvent`: match ownership; scoring side, recorded timestamp
- [x] Scores: event counts by side
- [x] Household team name is configuration, not persisted domain data
- [x] Excluded: players, scorers, assists, match minutes, individual statistics
- [x] Excluded: teams and seasons

## Screens

- [x] Login and logout
- [x] Public match list
- [x] Match create and edit form
- [x] Match score-entry screen
- [x] Public read-only match detail and score-event history

## Non-Goals

- [x] Native mobile apps
- [x] JavaScript SPA
- [x] Offline queues and synchronization
- [x] Realtime multi-parent score editing
- [x] Player statistics and scorer tracking
- [x] League tables, standings, fixture imports, calendar synchronization
- [x] Team management
- [x] Season management
- [x] Dedicated public sharing links or access tokens
- [x] Kubernetes and production deployment configuration

## Iteration 1: Single-Team Match Tracking

### Acceptance Criteria

- [x] Local application startup through Docker Compose
- [x] Configured household team name defaults to `K.F.C. Sparta Kolmont`
- [x] Team name can be overridden through the environment
- [x] Phone-sized match creation and goal recording
- [x] Home is selected for a new match without requiring an extra click
- [x] Displayed score equal to persisted score events
- [x] Most-recent accidental goal undo
- [x] Anonymous users can browse all matches and click through to read-only match details
- [x] Anonymous users cannot create, edit, delete, score, or undo matches
- [x] Authenticated users cannot modify another user's matches or score events
- [x] Match results are ordered by date without season grouping

### Required Code Changes

- [x] Remove the `Team` and `Season` models and their forms, views, URLs, templates, admin registrations, and tests
- [x] Add direct user ownership to `Match`
- [x] Regenerate migrations and reset the disposable local database instead of migrating existing data
- [x] Replace season-scoped match creation with direct authenticated match creation
- [x] Replace team and season navigation with match-focused navigation
- [x] Make match list and match detail views public and read-only
- [x] Keep score entry, goal creation, undo, editing, and deletion authenticated and owner-scoped
- [x] Load `TEAM_NAME` with `django-environ` and expose it to templates
- [x] Render the configured team name on the correct home or away side
- [x] Default new match forms to home
- [x] Explicitly select Pico's light color scheme to prevent unreadable light text on light backgrounds
- [x] Remove Python properties from application models
- [x] Calculate scores with explicit ORM annotations or view context values
- [x] Prefer namespaced imports, such as `import tracker.models` with `tracker.models.Match`
- [x] Keep `django-stubs` enabled with the Django mypy plugin
- [x] Keep strict mypy checks enforced in project configuration and verification
- [x] Add focused tests for public access, write protection, ownership, team-name rendering, and home defaults

## Iteration 2: Match Form Simplification

### Required Changes

- [x] Add a `Log in` link to public navigation for anonymous visitors
- [x] Remove venue location entirely from the model, forms, templates, JavaScript, tests, and migration schema
- [x] Pre-populate the date field when editing an existing match
- [x] Update completed and pending iteration items with Markdown checkboxes
- [x] Make `ScoreEvent.Side` labels lazy translations, replace `get_side_display()` with enum-label lookup, and test score-event display text
- [x] Replace `from typing import Any` with `import typing` and query the typed `ScoreEvent` manager directly for the latest undoable event
- [x] Upgrade Django to 6.1 with matching `django-stubs` and `django-stubs-ext` versions, regenerate the lockfile, and verify the full project suite

## Iteration 3: Match Form Refinement

- [x] Default a new match date to today
- [x] Keep match notes out of the main form by default

## Iteration 4: Private Release Basics

- [x] Add the private-use disclaimer
- [x] Use django-whitenoise to serve static assets

## Iteration 5: Continuous Delivery

- [ ] Set up the public GitHub repository and required configuration.
- [ ] Set up a GitHub Actions pipeline for tests, linting, type checks, and Docker image publishing.
- [ ] Set up a release process where merges to `master` create a CalVer-type release; deployment remains manual.
