from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone, translation

import tracker.models


def make_team(
    club_name: str = "United",
    *,
    age_group: str = "U11",
) -> tracker.models.Team:
    club = tracker.models.Club.objects.create(name=club_name)
    season, _ = tracker.models.Season.objects.get_or_create(
        name="2026-2027",
        defaults={"start_date": date(2026, 7, 1), "end_date": date(2027, 6, 30)},
    )
    return tracker.models.Team.objects.create(
        club=club,
        season=season,
        age_group=age_group,
    )


def make_match() -> tracker.models.Match:
    return tracker.models.Match.objects.create(
        home_team=make_team("Sparta Kolmont"),
        away_team=make_team(),
        match_date=date(2026, 8, 16),
    )


@pytest.mark.django_db
def test_matches_are_ordered_by_latest_date() -> None:
    earlier = make_match()
    later = tracker.models.Match.objects.create(
        home_team=earlier.home_team,
        away_team=make_team("City"),
        match_date=date(2026, 8, 17),
    )

    assert list(tracker.models.Match.objects.all()) == [later, earlier]


@pytest.mark.django_db
def test_score_events_are_ordered_most_recent_first() -> None:
    match = make_match()
    earlier = tracker.models.ScoreEvent.objects.create(
        match=match,
        side=tracker.models.ScoreEvent.Side.HOME,
        recorded_at=timezone.now() - timedelta(minutes=1),
    )
    later = tracker.models.ScoreEvent.objects.create(
        match=match,
        side=tracker.models.ScoreEvent.Side.AWAY,
        recorded_at=timezone.now(),
    )

    assert list(match.score_events.all()) == [later, earlier]


@pytest.mark.django_db
def test_score_event_display_uses_translated_side_label() -> None:
    event = tracker.models.ScoreEvent.objects.create(
        match=make_match(),
        side=tracker.models.ScoreEvent.Side.HOME,
    )

    with translation.override("en"):
        assert str(event) == f"Home goal at {event.recorded_at}"


@pytest.mark.django_db
def test_club_names_are_unique_case_insensitively() -> None:
    tracker.models.Club.objects.create(name="United")

    with pytest.raises(IntegrityError), transaction.atomic():
        tracker.models.Club.objects.create(name="united")


@pytest.mark.django_db
def test_team_identity_is_unique_within_club_and_season() -> None:
    team = make_team()

    with pytest.raises(IntegrityError), transaction.atomic():
        tracker.models.Team.objects.create(
            club=team.club,
            season=team.season,
            age_group=team.age_group,
            designation="",
        )


@pytest.mark.django_db
def test_match_defaults_to_scheduled_and_requires_distinct_teams() -> None:
    team = make_team()
    match = tracker.models.Match(
        home_team=team,
        away_team=team,
        match_date=date(2026, 8, 16),
    )

    assert match.status == tracker.models.Match.Status.SCHEDULED
    with pytest.raises(ValidationError, match="must differ"):
        match.full_clean()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("household_is_home", "opponent_side"),
    [
        (True, tracker.models.ScoreEvent.Side.AWAY),
        (False, tracker.models.ScoreEvent.Side.HOME),
    ],
)
def test_scorer_must_belong_to_scoring_team(
    household_is_home: bool,
    opponent_side: tracker.models.ScoreEvent.Side,
) -> None:
    household_team = make_team("Sparta Kolmont")
    opponent_team = make_team()
    match = tracker.models.Match.objects.create(
        home_team=household_team if household_is_home else opponent_team,
        away_team=opponent_team if household_is_home else household_team,
        match_date=date(2026, 8, 16),
    )
    player = tracker.models.Player.objects.create(name="Alex")
    tracker.models.TeamMembership.objects.create(player=player, team=household_team)
    event = tracker.models.ScoreEvent(
        match=match,
        side=opponent_side,
        scorer=player,
    )

    with pytest.raises(ValidationError, match="scoring team"):
        event.full_clean()


@pytest.mark.django_db
def test_score_event_occurrence_time_is_optional() -> None:
    event = tracker.models.ScoreEvent.objects.create(
        match=make_match(),
        side=tracker.models.ScoreEvent.Side.HOME,
    )

    assert event.occurred_at is None


@pytest.mark.django_db
def test_match_teams_must_belong_to_same_season() -> None:
    match = make_match()
    other_season = tracker.models.Season.objects.create(
        name="2025-2026",
        start_date=date(2025, 7, 1),
        end_date=date(2026, 6, 30),
    )
    match.away_team = tracker.models.Team.objects.create(
        club=match.away_team.club,
        season=other_season,
        age_group="U10",
    )

    with pytest.raises(ValidationError, match="same season"):
        match.full_clean()
