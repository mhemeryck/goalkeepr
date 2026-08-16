# Goalkeepr Analysis

## Background

Both children play football, and their family regularly attends their matches.

At present, another parent records match scores manually in an Excel spreadsheet on a phone during games.

That spreadsheet becomes the historical record of all completed matches after each game.

Goalkeepr will replace this phone-based manual spreadsheet workflow with a small, purpose-built application.

The primary user is a parent recording the score while watching a match.

The application must therefore make the in-match action faster and less error-prone than editing a spreadsheet on a phone.

The project should stay intentionally small so it can be built in one focused implementation pass and maintained with little effort.

## Technical Direction

Goalkeepr will be a Django application using server-rendered HTML and HTMX for small interactive updates.

It will use PostgreSQL for durable application data.

The first release runs locally with Docker Compose, which starts the Django application and PostgreSQL.

This matches the existing technical approach used by `facturette` without prematurely adding deployment work.

Kubernetes deployment, ingress, TLS, image publishing, backups, and production secrets are follow-up work.

## Users And Access

The first release supports normal Django user accounts.

One shared household account is sufficient for initial use.

The data model should allow further users and per-team permissions later without building shared collaboration now.

Every user must only be able to access their own teams and match data.

## MVP Scope

- Manage teams for both children.
- Organize matches into seasons.
- Create a match with date, opponent, home or away status, and optional notes.
- Start and finish a match.
- Record a score event for either side using large phone-friendly controls.
- Undo the most recent score event for either side.
- Derive and display the current and final score from score events.
- Browse completed results for a team and season.
- Edit or delete a match when correcting historical data.
- Authenticate users before showing or changing data.

## Score Recording Flow

The parent opens a scheduled or newly created match from a phone.

The match screen prominently shows both team names and the current score.

Large controls add a goal for Goalkeepr's team or the opponent.

Each tap persists an individual timestamped score event rather than only overwriting a score total.

The screen provides a clear undo action so an accidental tap can be corrected immediately.

Finishing a match makes its derived score part of the season history.

## Initial Data Model

`Team` represents one of the children's football teams and belongs to a user.

`Season` represents a named season for one team.

`Match` belongs to a season and stores the opponent, date, home or away status, status, and optional notes.

`ScoreEvent` belongs to a match and records which side scored and when it was recorded.

The score is calculated by counting the match's score events by side.

Player names, scorers, assists, match minutes, and other individual statistics are not part of the initial model.

## Screens

- Login and logout.
- Team list.
- Season and match list.
- Create and edit match form.
- Live match score-entry screen.
- Completed match detail and score-event history.

## Non-Goals

- Native mobile applications.
- A JavaScript single-page application.
- Offline score queueing and synchronization.
- Realtime multi-parent score editing.
- Player statistics or goal-scorer tracking.
- League tables, standings, fixtures import, or calendar synchronization.
- Public sharing links.
- Kubernetes or other production deployment configuration.

## Acceptance Criteria

- A user can run the application locally with Docker Compose.
- A user can create separate teams and seasons for both children.
- A user can create a match and record goals on a phone-sized viewport.
- The displayed score always matches the persisted score events.
- An accidental most-recent goal can be undone.
- Finished matches appear with their final result in the relevant season history.
- A user cannot view or alter another user's teams, seasons, matches, or score events.
