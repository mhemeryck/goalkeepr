import pytest
from django.contrib.auth.models import User

import tracker.models


@pytest.fixture
def user(db: None) -> User:
    return User.objects.create_user(username="parent", password="secret-pass")


@pytest.fixture
def other_user(db: None) -> User:
    return User.objects.create_user(username="other", password="secret-pass")


@pytest.fixture
def season() -> tracker.models.Season:
    return tracker.models.Season.YEAR_2026


@pytest.fixture
def primary_team(season: tracker.models.Season) -> tracker.models.Team:
    club, _ = tracker.models.Club.objects.get_or_create(name="K.F.C. Sparta Kolmont")
    team, _ = tracker.models.Team.objects.get_or_create(
        club=club,
        season=season,
        age_group="U11",
    )
    tracker.models.Defaults.objects.update_or_create(
        pk=1,
        defaults={"default_team": team},
    )
    return team


@pytest.fixture
def opponent_team(season: tracker.models.Season) -> tracker.models.Team:
    club, _ = tracker.models.Club.objects.get_or_create(name="United")
    team, _ = tracker.models.Team.objects.get_or_create(
        club=club,
        season=season,
        age_group="U11",
    )
    return team
