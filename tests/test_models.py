from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

import tracker.models


@pytest.mark.django_db
def test_matches_are_ordered_by_latest_date(user: User) -> None:
    earlier = tracker.models.Match.objects.create(
        owner=user,
        opponent_name="United",
        match_date=date(2026, 8, 16),
    )
    later = tracker.models.Match.objects.create(
        owner=user,
        opponent_name="City",
        match_date=date(2026, 8, 17),
    )

    assert list(tracker.models.Match.objects.all()) == [later, earlier]


@pytest.mark.django_db
def test_score_events_are_ordered_most_recent_first(user: User) -> None:
    match = tracker.models.Match.objects.create(
        owner=user,
        opponent_name="United",
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
