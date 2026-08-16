from collections.abc import Callable
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from tracker.models import Match, ScoreEvent, Season, Team


def make_match(owner: User, *, is_home: bool = True) -> Match:
    team = Team.objects.create(owner=owner, name="Falcons")
    season = Season.objects.create(team=team, name="2026-27")
    return Match.objects.create(
        season=season,
        opponent_name="United",
        match_date=date(2026, 8, 16),
        is_home=is_home,
    )


@pytest.mark.django_db
def test_match_list_requires_login(client: Client) -> None:
    response = client.get(reverse("match-list"))

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("login"))


@pytest.mark.django_db
def test_match_list_only_contains_owned_matches(
    user: User,
    other_user: User,
    client_for: Callable[[User], Client],
) -> None:
    owned = make_match(user)
    hidden = make_match(other_user)

    response = client_for(user).get(reverse("match-list"))

    assert response.status_code == 200
    assert owned in response.context["matches"]
    assert hidden not in response.context["matches"]


@pytest.mark.django_db
def test_team_create_assigns_authenticated_owner(
    user: User,
    client_for: Callable[[User], Client],
) -> None:
    response = client_for(user).post(reverse("team-create"), {"name": "Falcons"})

    team = Team.objects.get()
    assert response.status_code == 302
    assert team.owner == user


@pytest.mark.django_db
def test_season_create_is_limited_to_owned_team(
    user: User,
    other_user: User,
    client_for: Callable[[User], Client],
) -> None:
    other_team = Team.objects.create(owner=other_user, name="Other")

    response = client_for(user).post(
        reverse("season-create", args=[other_team.pk]),
        {"name": "2026-27"},
    )

    assert response.status_code == 404
    assert not Season.objects.exists()


@pytest.mark.django_db
def test_match_create_assigns_owned_season(
    user: User,
    client_for: Callable[[User], Client],
) -> None:
    team = Team.objects.create(owner=user, name="Falcons")
    season = Season.objects.create(team=team, name="2026-27")

    response = client_for(user).post(
        reverse("match-create", args=[season.pk]),
        {
            "opponent_name": "United",
            "match_date": "2026-08-16",
            "is_home": "True",
            "location": "Sports field",
            "notes": "Cup match",
        },
    )

    match = Match.objects.get()
    assert response.status_code == 302
    assert match.season == season
    assert match.opponent_name == "United"


@pytest.mark.django_db
def test_match_detail_rejects_another_users_match(
    user: User,
    other_user: User,
    client_for: Callable[[User], Client],
) -> None:
    match = make_match(other_user)

    response = client_for(user).get(reverse("match-detail", args=[match.pk]))

    assert response.status_code == 404


@pytest.mark.django_db
def test_goal_records_event_and_returns_score_fragment(
    user: User,
    client_for: Callable[[User], Client],
) -> None:
    match = make_match(user)

    response = client_for(user).post(
        reverse("score-goal", args=[match.pk, ScoreEvent.Side.HOME]),
        HTTP_HX_REQUEST="true",
    )

    event = ScoreEvent.objects.get()
    assert response.status_code == 200
    assert event.match == match
    assert event.side == ScoreEvent.Side.HOME
    assert [template.name for template in response.templates] == [
        "tracker/partials/scoreboard.html"
    ]
    assert response.context["home_score"] == 1
    assert response.context["away_score"] == 0


@pytest.mark.django_db
def test_goal_rejects_invalid_side(
    user: User,
    client_for: Callable[[User], Client],
) -> None:
    match = make_match(user)

    response = client_for(user).post(
        reverse("score-goal", args=[match.pk, "invalid"]),
    )

    assert response.status_code == 404
    assert not ScoreEvent.objects.exists()


@pytest.mark.django_db
def test_goal_rejects_another_users_match(
    user: User,
    other_user: User,
    client_for: Callable[[User], Client],
) -> None:
    match = make_match(other_user)

    response = client_for(user).post(
        reverse("score-goal", args=[match.pk, ScoreEvent.Side.HOME]),
    )

    assert response.status_code == 404
    assert not ScoreEvent.objects.exists()


@pytest.mark.django_db
def test_undo_removes_most_recent_event_for_selected_side(
    user: User,
    client_for: Callable[[User], Client],
) -> None:
    match = make_match(user)
    first_home = ScoreEvent.objects.create(match=match, side=ScoreEvent.Side.HOME)
    away = ScoreEvent.objects.create(match=match, side=ScoreEvent.Side.AWAY)
    latest_home = ScoreEvent.objects.create(match=match, side=ScoreEvent.Side.HOME)

    response = client_for(user).post(
        reverse("score-undo", args=[match.pk, ScoreEvent.Side.HOME]),
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert list(ScoreEvent.objects.all()) == [away, first_home]
    assert not ScoreEvent.objects.filter(pk=latest_home.pk).exists()
    assert response.context["home_score"] == 1
    assert response.context["away_score"] == 1


@pytest.mark.django_db
def test_undo_with_no_event_is_idempotent(
    user: User,
    client_for: Callable[[User], Client],
) -> None:
    match = make_match(user)

    response = client_for(user).post(
        reverse("score-undo", args=[match.pk, ScoreEvent.Side.AWAY]),
    )

    assert response.status_code == 200
    assert not ScoreEvent.objects.exists()


@pytest.mark.django_db
def test_match_edit_updates_owned_match(
    user: User,
    client_for: Callable[[User], Client],
) -> None:
    match = make_match(user)

    response = client_for(user).post(
        reverse("match-edit", args=[match.pk]),
        {
            "opponent_name": "City",
            "match_date": "2026-08-17",
            "is_home": "False",
            "location": "",
            "notes": "",
        },
    )

    match.refresh_from_db()
    assert response.status_code == 302
    assert match.opponent_name == "City"
    assert match.is_home is False


@pytest.mark.django_db
def test_match_delete_requires_post_and_removes_owned_match(
    user: User,
    client_for: Callable[[User], Client],
) -> None:
    match = make_match(user)
    client = client_for(user)
    url = reverse("match-delete", args=[match.pk])

    confirmation = client.get(url)
    response = client.post(url)

    assert confirmation.status_code == 200
    assert response.status_code == 302
    assert not Match.objects.exists()
