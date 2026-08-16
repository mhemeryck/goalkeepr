# Goalkeepr Analysis

## Background

- Youth football score recording for two children
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
- Future-ready model for more users and per-team permissions
- Strict user ownership for teams, seasons, matches, and score events

## MVP Scope

- Team management for both children
- Seasons per team
- Match creation: date, opponent, home or away, optional notes
- Match start and finish
- Large score controls for either side
- Timestamped score events
- Most-recent score-event undo for either side
- Derived current and final scores
- Completed-result browsing by team and season
- Historical match editing and deletion
- Finished matches remain editable
- Authentication before data access or changes

## Score Recording Flow

- Scheduled or newly created match opened on a phone
- Prominent team names and current score
- Large goal controls: Goalkeepr team and opponent
- Persistent timestamped event per tap
- Immediate undo for accidental taps
- Finished match result in season history

## Initial Data Model

- `Team`: child team; user ownership
- `Season`: team ownership; free-text name
- `Match`: season ownership; opponent, date, home or away, status, optional notes
- `ScoreEvent`: match ownership; scoring side, recorded timestamp
- Scores: event counts by side
- Excluded: players, scorers, assists, match minutes, individual statistics

## Screens

- Login and logout
- Team list
- Season and match list
- Match create and edit form
- Live score-entry screen
- Completed-match detail and score-event history

## Non-Goals

- Native mobile apps
- JavaScript SPA
- Offline queues and synchronization
- Realtime multi-parent score editing
- Player statistics and scorer tracking
- League tables, standings, fixture imports, calendar synchronization
- Public sharing links
- Kubernetes and production deployment configuration

## Acceptance Criteria

- Local application startup through Docker Compose
- Separate teams and seasons for both children
- Phone-sized match creation and goal recording
- Displayed score equal to persisted score events
- Most-recent accidental goal undo
- Finished results in season history
- No cross-user viewing or modification of teams, seasons, matches, or score events
