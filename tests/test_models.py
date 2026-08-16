from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.utils import timezone

from tracker.models import Match, ScoreEvent, Season, Team


@pytest.mark.django_db
def test_match_scores_are_derived_from_events(user: User) -> None:
    team = Team.objects.create(owner=user, name="Falcons")
    season = Season.objects.create(team=team, name="2026-27")
    match = Match.objects.create(
        season=season,
        opponent_name="United",
        match_date=date(2026, 8, 16),
        is_home=True,
    )

    ScoreEvent.objects.create(match=match, side=ScoreEvent.Side.HOME)
    ScoreEvent.objects.create(match=match, side=ScoreEvent.Side.HOME)
    ScoreEvent.objects.create(match=match, side=ScoreEvent.Side.AWAY)

    assert match.home_score == 2
    assert match.away_score == 1


@pytest.mark.django_db
def test_score_events_are_ordered_most_recent_first(user: User) -> None:
    team = Team.objects.create(owner=user, name="Falcons")
    season = Season.objects.create(team=team, name="2026-27")
    match = Match.objects.create(
        season=season,
        opponent_name="United",
        match_date=date(2026, 8, 16),
        is_home=True,
    )
    earlier = ScoreEvent.objects.create(
        match=match,
        side=ScoreEvent.Side.HOME,
        recorded_at=timezone.now() - timedelta(minutes=1),
    )
    later = ScoreEvent.objects.create(
        match=match,
        side=ScoreEvent.Side.AWAY,
        recorded_at=timezone.now(),
    )

    assert list(match.score_events.all()) == [later, earlier]


@pytest.mark.django_db
def test_season_names_are_unique_per_team(user: User) -> None:
    team = Team.objects.create(owner=user, name="Falcons")
    Season.objects.create(team=team, name="2026-27")

    with pytest.raises(IntegrityError):
        Season.objects.create(team=team, name="2026-27")
