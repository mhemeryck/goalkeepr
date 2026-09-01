# Match Domain

## Purpose

Goalkeepr records youth football matches for its primary club.
This document defines the durable match-domain concepts before the model expands to cover historical data, fixtures, competitions, and tournaments.
It is the design source of truth for these concepts.
`docs/analysis.md` remains the chronological product and iteration record.

## Domain Terms

- Primary club: the club this Goalkeepr installation serves.
- Club: an enduring football organization that has teams across seasons and age groups.
- Team: a club's team for one season and age group, with an optional designation such as `A`.
- Player: a team player who can be attributed to a score event.
- Match: one fixture between a home team and an away team.
- Fixture: a match that is scheduled but has not been completed.
- Result: the known final score of a completed match.
- Score event: one goal by either side.
- Competition: a set of related fixtures, such as a league or series.
- Tournament: a competition event that groups multiple matches under shared context.

## Target Model

- `Club` represents a football organization and is unique case-insensitively by name.
- `Season` represents an explicitly date-bounded period.
  Its boundaries support one or two competition phases without changing the model.
- `Team` belongs to one club and season, and records its age group and optional designation.
- `Match` has required `home_team` and `away_team` relationships, a match date, optional notes, and an explicit status.
  The home and away teams must differ.
- `Competition` groups a team's longer-running seasonal fixtures and records its level where known.
- `Tournament` groups its short-lived child matches and records their shared name, date, and location.
- A match may belong to a competition or tournament when that context is known.
- `ScoreEvent` stores its match, scoring side, optional scorer, `recorded_at`, and nullable `occurred_at` timestamp.
- Current and final scores are derived by counting score events for each side.

## Club Context And User Defaults

- The `PRIMARY_CLUB_NAME` setting identifies the club this installation serves.
  It is not a claim that the club is the home side in every fixture.
- Each user has a changeable default team belonging to the primary club.
- New-match entry pre-fills the user's default team, so age group selection is not repeated for every fixture.
- The scorekeeper must still explicitly record whether that team is the home or away side, because this is a fact of each fixture.

## Historical Results

The historical workbook records final scores for many matches.
It does not record individual scorers, goal order, or goal times.

- A known final score is still a factual result.
- Historical results must not invent player attribution, event order, or occurrence times.
- Historical score events are anonymous, retain their known scoring side, and leave `occurred_at` and `scorer` empty.
- Imported historical matches need clear source provenance and an idempotent import path.
- Cancelled, incomplete, and ambiguous workbook rows must be reported rather than guessed.

## Score Events And Time

Score events distinguish the time Goalkeepr stored an event from the time a goal occurred.

- `recorded_at` is required and records when Goalkeepr captured or imported the event.
- `occurred_at` is optional and records when the goal happened in the match.
- Live score entry initially records both timestamps at the time of entry.
- Historical imports set `recorded_at` while leaving `occurred_at` and `scorer` empty.
- A missing `occurred_at` means the goal contributes to the result but has no displayable timeline position.
- The UI must not render a fabricated timestamped history for undetailed historical events.

## Competition And Tournament Context

The workbook contains league fixtures and tournaments.
Tournament headings provide shared date and location context for several child matches.

- Matches must not be imported as one undifferentiated historical list.
- Competition and tournament context belong to the match domain.
- Tournament grouping must associate its child matches without treating the heading itself as a match.

## Match Lifecycle

- Every match has one explicit status: `scheduled`, `live`, `finished`, or `cancelled`.
- New matches start as `scheduled`.
- A scorekeeper explicitly starts, finishes, or cancels a match.
  Status changes are not inferred from score events.
- Score events remain editable after a match is `finished`.
  Finished means the result is currently considered final; it does not lock the match.
- Only `finished` matches contribute to wins, draws, losses, completed-match totals, and other result statistics.
- `scheduled`, `live`, and `cancelled` matches have no result label and must not be displayed or counted as draws.

## Boundaries

- Players and score events remain optional match detail.
- A complete result must not require known players, scorers, or occurrence times.
- Match media may later attach authorized photos to a match without becoming a social feed.
- Assists, lineups, positions, and other event types require evidence from real use before they are modelled.
- Generic match events are deferred until a second concrete event type has shared requirements with score events.
  A type field alone would not model the distinct data required for goals, cards, or substitutions.
