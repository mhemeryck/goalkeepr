from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone, translation

import tracker.models


def make_team(name: str = "United") -> tracker.models.Team:
    return tracker.models.Team.objects.create(name=name)


@pytest.mark.django_db
def test_matches_are_ordered_by_latest_date() -> None:
    earlier = tracker.models.Match.objects.create(
        opponent=make_team(),
        match_date=date(2026, 8, 16),
    )
    later = tracker.models.Match.objects.create(
        opponent=make_team("City"),
        match_date=date(2026, 8, 17),
    )

    assert list(tracker.models.Match.objects.all()) == [later, earlier]


@pytest.mark.django_db
def test_score_events_are_ordered_most_recent_first() -> None:
    match = tracker.models.Match.objects.create(
        opponent=make_team(),
        match_date=date(2026, 8, 16),
    )
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
    match = tracker.models.Match.objects.create(
        opponent=make_team(),
        match_date=date(2026, 8, 16),
    )
    event = tracker.models.ScoreEvent.objects.create(
        match=match,
        side=tracker.models.ScoreEvent.Side.HOME,
    )

    with translation.override("en"):
        assert str(event) == f"Home goal at {event.recorded_at}"


@pytest.mark.django_db
def test_team_names_are_unique_case_insensitively() -> None:
    make_team("United")

    with pytest.raises(IntegrityError), transaction.atomic():
        make_team("united")


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("is_home", "opponent_side"),
    [
        (True, tracker.models.ScoreEvent.Side.AWAY),
        (False, tracker.models.ScoreEvent.Side.HOME),
    ],
)
def test_opponent_goal_rejects_scorer(
    is_home: bool,
    opponent_side: tracker.models.ScoreEvent.Side,
) -> None:
    match = tracker.models.Match.objects.create(
        opponent=make_team(),
        match_date=date(2026, 8, 16),
        is_home=is_home,
    )
    event = tracker.models.ScoreEvent(
        match=match,
        side=opponent_side,
        scorer=tracker.models.Player.objects.create(name="Alex"),
    )

    with pytest.raises(ValidationError, match="household-team goals"):
        event.full_clean()
