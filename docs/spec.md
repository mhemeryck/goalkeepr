# Goalkeepr Product Specification

Single source of truth for current behaviour and intended direction

GitHub issues for implementation tracking
Git history for superseded requirements and previous iterations
GitHub issue #13 as an idea inbox rather than committed scope

## Product

- Small, mobile-first youth football score recorder
- Primary user: parent recording a match one-handed on a phone
- Primary interaction: fast and resilient score entry
- One shared household context
- Default club, season, and age group resolving to an explicit household team
- Explicit home and away teams retained on every match
- Server-rendered Django with progressive HTMX enhancement
- URL-backed navigation, filtering, and pagination
- Ordinary HTML forms as the baseline for mutations

## Users And Access

- Public match lists and match details
- Authentication for match creation, editing, deletion, scoring, and lifecycle changes
- Shared access for authenticated household users
- No per-user match ownership
- No public registration or account-management workflow
- Public visibility of youth player names still undecided

## Domain

### Clubs, Teams, And Defaults

- Club: enduring football organization with a case-insensitively unique name
- Team: one club, season, and age group
- Seasons: fixed start years from 2022 through 2033
- Season label: `YYYY-YYYY+1`
- Season boundaries: 1 July through 30 June
- Age groups: fixed choices from `U6` through `U18`
- At most one team for each club, season, and age-group combination
- One application-defaults record
- Defaults required to resolve to an existing team before ordinary match creation

### Players And Memberships

- Player: case-insensitively unique name
- Team membership: explicit player-to-team association
- Household roster derived from team memberships
- Scorer choices derived from the household roster
- No implicit opponent membership from scorer creation or selection
- No deletion of retained scorer attribution or membership history
- Dependency-protected deletion until archival lifecycle requirements emerge

### Matches

- Distinct home and away teams from the same season
- Match date, optional notes, and explicit lifecycle state
- Lifecycle states: `scheduled`, `live`, `finished`, and `cancelled`
- Initial state: `scheduled`
- Supported transitions
  - `scheduled` to `live` or `cancelled`
  - `live` to `finished` or `cancelled`
  - `finished` to `live`
  - `cancelled` to `scheduled`
- Explicit status changes independent from score events and dates
- Final-result statistics derived only from finished matches
- Separate deliberate flow for historical results

### Score Events

- Score derived from score-event counts for each side
- No mutable score counters
- Required match, scoring side, and `recorded_at`
- Optional scorer and `occurred_at`
- Scorer membership required in the scoring team
- Anonymous opponent goals in the ordinary household workflow
- `recorded_at`: storage time
- `occurred_at`: known goal time
- No invented scorer, order, or occurrence-time data

## Planned Workflows

The workflows in this section describe the intended product direction and are not all implemented in the current release.

### Match List

- Default household team and season context
- Latest matches first
- Live scores where applicable
- Search by opponent club, age group, and season
- URL-backed season and lifecycle filters
- Explicit `All seasons` option
- URL-backed `Load more` pagination with HTMX enhancement
- Additional team context only where needed for disambiguation

### Add Match

- Resolved household team against an explicitly selected opponent team
- Opponents limited to the configured season and age group
- Home or away position, date, and optional notes
- New matches always scheduled
- No status control in ordinary creation
- In-page HTMX opponent-team creation
- Standalone opponent-team form as fallback
- Preserved match fields while adding an opponent
- Editable prefilled season and age-group context
- Future advanced flow for different household teams, age groups, neutral fixtures, or neither default participant

### Match Detail And Score Entry

- Dominant score display
- Prominent lifecycle state and primary next action
- Start or cancel for scheduled matches
- Finish or cancel for live matches
- Correct or reopen for finished matches
- Restore for cancelled matches
- Explicit correction mode for finished scores
- Side-labelled goal controls with stable identifiers
- Disabled score controls during pending HTMX requests
- Household scorer selection from the team roster
- `No scorer recorded` as the meaningful empty choice
- Player creation or reuse without recording a goal
- Dedicated atomic score-status region
- Scoreboard-only polling for anonymous live-match viewers
- No polling after finish or cancellation
- Explicit Edit, Save, and Cancel actions for match fields
- No persistence from focus movement
- Confirmed side swapping including existing score-event sides

### Setup

- Authenticated management of clubs, teams, players, and defaults
- Root-level ID-backed club and team URLs
- Club pages grouped by season
- Team pages with club, season, age group, roster, matches, and results
- Independent shared-club editing
- Full team form for club, season, and age group
- Temporary `Manage` navigation disclosure
- Planned clear `Setup` destination for every management workflow

## Historical Data Iteration

### Outcome

- Safe ingestion of the existing scorekeeper workbook
- Useful historical fixtures and results alongside native Goalkeepr matches
- Realistic dataset for validating the domain, navigation, filtering, pagination, and statistics

### Source Interpretation

- Completed matches, fixtures, competitions, and tournaments across seasons and age groups
- Tournament headings as shared context rather than matches
- Potentially missing scorers, goal order, goal times, and other details
- Explicit reporting for cancelled, incomplete, and ambiguous rows
- Documented workbook mapping and exceptional row shapes before import implementation
- Representative source fixtures for normal and exceptional cases

### Import Requirements

- Explicit management operation or command
- No implicit import during application startup
- Dry-run report without application-data changes
- Proposed creations, matches, warnings, ambiguities, and rejected rows in the report
- Idempotent repeated imports
- No duplicate domain records or score events
- Provenance identifying workbook, worksheet, and row or equivalent stable source identity
- Deliberate case-insensitive club and team matching
- Explicit resolution for ambiguous matches
- Atomic import where practical
- No unreviewable partial dataset after failure
- Database backup before production import or related production schema migration

### Historical Results

- Known final score treated as factual despite missing goal details
- Anonymous score events permitted for preserving the derived-score invariant
- No scorer or `occurred_at` on aggregate historical events
- No fabricated chronological goal history
- Lifecycle state based only on reliable source information
- Retained source provenance for correction and repeat imports

### Competition And Tournament Context

- Competition grouping for related seasonal fixtures where supported by the workbook
- Tournament grouping for short-lived child matches under shared event context
- Optional competition and tournament context where unknown
- No inferred tables, rounds, or classifications absent from the workbook

### Historical Presentation

- Historical matches in normal search, filters, pagination, team pages, and statistics
- Clear distinction between aggregate imported results and detailed live goal timelines
- No presentation of missing scorer or occurrence-time information as known
- Competition and tournament context without changing canonical match URLs
- Usable long names and dense historical data at a 320-pixel viewport

## Remaining Product Work

Dependency order rather than duplicated issue-level tracking

1. Model-boundary integrity for scorers, memberships, teams, and defaults
2. Workbook mapping and dry-run validation
3. Import provenance and idempotent ingestion
4. Source-backed competition and tournament context
5. Honest presentation of aggregate historical results
6. Clear `Setup` destination replacing the management disclosure
7. Match-detail focus restoration, panel styling, destructive actions, and HTMX failure states
8. Advanced participant and deliberate historical-result entry flows

## Accessibility And Resilience

- Touch targets of at least 44 pixels for primary and destructive controls
- Wrapping or collapsing navigation under narrow screens and text zoom
- Interactive elements discoverable without hover or color alone
- Current-page state for primary destinations and descendants
- Field-associated and announced validation errors
- Compact HTMX pending, network-error, and stale-data states
- No focus theft during HTMX interactions
- Semantic `time` elements for match dates
- Safe wrapping for long club and team names
- Usable non-HTMX path for every enhanced workflow

## Open Decisions

- Public visibility of youth player names
- Advanced workflow outside the default household-team context
- Individual historical-result entry outside workbook import
- Archival states after dependency-protected deletion becomes insufficient
- Competition and tournament identity across workbook variants

## Non-Goals

- JavaScript SPA or separate frontend API
- Native mobile applications
- Offline synchronization
- Realtime multi-scorekeeper coordination
- Invented appearances, playing time, positions, assists, lineups, or event chronology
- League tables or standings without complete and reliable source data
- Social networking around match media
- Implementation of issue #13 ideas before promotion to focused issues
