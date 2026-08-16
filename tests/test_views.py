from collections.abc import Callable
from datetime import date

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, override_settings
from django.urls import reverse

import tracker.models


def make_match(
    owner: User,
    *,
    opponent_name: str = "United",
    is_home: bool = True,
) -> tracker.models.Match:
    return tracker.models.Match.objects.create(
        owner=owner,
        opponent_name=opponent_name,
        match_date=date(2026, 8, 16),
        is_home=is_home,
    )


@pytest.mark.django_db
def test_match_list_is_public_and_contains_all_matches(
    client: Client,
    user: User,
    other_user: User,
) -> None:
    first = make_match(user)
    second = make_match(other_user, opponent_name="City")

    response = client.get(reverse("match-list"))

    assert response.status_code == 200
    assert list(response.context["matches"]) == [second, first]
    assert "K.F.C. Sparta Kolmont" in response.text
    assert reverse("match-detail", args=[first.pk]) in response.text
    assert reverse("match-score", args=[first.pk]) not in response.text


@pytest.mark.django_db
def test_public_navigation_contains_login_link(client: Client) -> None:
    response = client.get(reverse("match-list"))

    assert reverse("login") in response.text


@pytest.mark.django_db
def test_match_list_contains_private_use_disclaimer(client: Client) -> None:
    response = client.get(reverse("match-list"))

    assert "Private household use only." in response.text


@pytest.mark.django_db
def test_match_list_uses_full_height_layout(client: Client) -> None:
    response = client.get(reverse("match-list"))

    assert '<main class="site-main container">' in response.text


def test_static_files_use_whitenoise() -> None:
    assert "whitenoise.middleware.WhiteNoiseMiddleware" in settings.MIDDLEWARE
    assert (
        settings.STORAGES["staticfiles"]["BACKEND"]
        == "whitenoise.storage.CompressedManifestStaticFilesStorage"
    )


@pytest.mark.django_db
def test_match_list_scores_are_derived_from_events(client: Client, user: User) -> None:
    match = make_match(user)
    tracker.models.ScoreEvent.objects.create(
        match=match, side=tracker.models.ScoreEvent.Side.HOME
    )
    tracker.models.ScoreEvent.objects.create(
        match=match, side=tracker.models.ScoreEvent.Side.HOME
    )
    tracker.models.ScoreEvent.objects.create(
        match=match, side=tracker.models.ScoreEvent.Side.AWAY
    )

    response = client.get(reverse("match-list"))

    listed_match = response.context["matches"][0]
    assert listed_match.home_score_value == 2
    assert listed_match.away_score_value == 1


@pytest.mark.django_db
def test_match_detail_is_public_and_read_only(client: Client, user: User) -> None:
    match = make_match(user)

    response = client.get(reverse("match-detail", args=[match.pk]))

    assert response.status_code == 200
    assert reverse("match-edit", args=[match.pk]) not in response.text
    assert reverse("match-delete", args=[match.pk]) not in response.text
    assert reverse("match-score", args=[match.pk]) not in response.text


@pytest.mark.django_db
@override_settings(TEAM_NAME="Configured FC")
@pytest.mark.parametrize(
    ("is_home", "heading"),
    [(True, "Configured FC 0–0 United"), (False, "United 0–0 Configured FC")],
)
def test_match_detail_places_configured_team_on_correct_side(
    client: Client,
    user: User,
    is_home: bool,
    heading: str,
) -> None:
    match = make_match(user, is_home=is_home)

    response = client.get(reverse("match-detail", args=[match.pk]))

    assert heading in response.text


@pytest.mark.django_db
def test_owner_sees_match_write_actions(
    user: User,
    client_for: Callable[[User], Client],
) -> None:
    match = make_match(user)

    response = client_for(user).get(reverse("match-detail", args=[match.pk]))

    assert reverse("match-edit", args=[match.pk]) in response.text
    assert reverse("match-delete", args=[match.pk]) in response.text
    assert reverse("match-score", args=[match.pk]) in response.text


@pytest.mark.django_db
def test_match_create_requires_login(client: Client) -> None:
    response = client.get(reverse("match-create"))

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("login"))


@pytest.mark.django_db
def test_match_create_defaults_to_home(
    user: User,
    client_for: Callable[[User], Client],
) -> None:
    response = client_for(user).get(reverse("match-create"))

    assert response.status_code == 200
    assert response.context["form"]["is_home"].value() is True
    assert "location" not in response.context["form"].fields


@pytest.mark.django_db
def test_match_create_defaults_date_to_today(
    user: User,
    client_for: Callable[[User], Client],
) -> None:
    response = client_for(user).get(reverse("match-create"))

    assert response.status_code == 200
    assert response.context["form"]["match_date"].value() == date.today()


@pytest.mark.django_db
def test_match_create_keeps_notes_collapsed_by_default(
    user: User,
    client_for: Callable[[User], Client],
) -> None:
    response = client_for(user).get(reverse("match-create"))

    assert response.status_code == 200
    assert "<details>" in response.text
    assert "<summary>Notes</summary>" in response.text


@pytest.mark.django_db
def test_match_create_assigns_owner(
    user: User,
    client_for: Callable[[User], Client],
) -> None:
    response = client_for(user).post(
        reverse("match-create"),
        {
            "opponent_name": "United",
            "match_date": "2026-08-16",
            "is_home": "True",
            "notes": "Cup match",
        },
    )

    match = tracker.models.Match.objects.get()
    assert response.status_code == 302
    assert match.owner == user


@pytest.mark.django_db
def test_match_edit_populates_date_field(
    user: User,
    client_for: Callable[[User], Client],
) -> None:
    match = make_match(user)

    response = client_for(user).get(reverse("match-edit", args=[match.pk]))

    assert response.status_code == 200
    assert 'value="2026-08-16"' in response.text


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("route_name", "method", "args"),
    [
        ("match-edit", "get", ()),
        ("match-delete", "post", ()),
        ("match-score", "get", ()),
        ("score-goal", "post", (tracker.models.ScoreEvent.Side.HOME,)),
        ("score-undo", "post", (tracker.models.ScoreEvent.Side.HOME,)),
    ],
)
def test_match_writes_require_login(
    client: Client,
    user: User,
    route_name: str,
    method: str,
    args: tuple[str, ...],
) -> None:
    match = make_match(user)
    url = reverse(route_name, args=(match.pk, *args))

    response = getattr(client, method)(url)

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("login"))


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("route_name", "method", "args"),
    [
        ("match-edit", "get", ()),
        ("match-delete", "post", ()),
        ("match-score", "get", ()),
        ("score-goal", "post", (tracker.models.ScoreEvent.Side.HOME,)),
        ("score-undo", "post", (tracker.models.ScoreEvent.Side.HOME,)),
    ],
)
def test_match_writes_reject_another_user(
    user: User,
    other_user: User,
    client_for: Callable[[User], Client],
    route_name: str,
    method: str,
    args: tuple[str, ...],
) -> None:
    match = make_match(other_user)
    url = reverse(route_name, args=(match.pk, *args))

    response = getattr(client_for(user), method)(url)

    assert response.status_code == 404


@pytest.mark.django_db
def test_goal_records_event_and_returns_score_fragment(
    user: User,
    client_for: Callable[[User], Client],
) -> None:
    match = make_match(user)

    response = client_for(user).post(
        reverse("score-goal", args=[match.pk, tracker.models.ScoreEvent.Side.HOME]),
        HTTP_HX_REQUEST="true",
    )

    event = tracker.models.ScoreEvent.objects.get()
    assert response.status_code == 200
    assert event.match == match
    assert event.side == tracker.models.ScoreEvent.Side.HOME
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
    assert not tracker.models.ScoreEvent.objects.exists()


@pytest.mark.django_db
def test_undo_removes_most_recent_event_for_selected_side(
    user: User,
    client_for: Callable[[User], Client],
) -> None:
    match = make_match(user)
    first_home = tracker.models.ScoreEvent.objects.create(
        match=match, side=tracker.models.ScoreEvent.Side.HOME
    )
    away = tracker.models.ScoreEvent.objects.create(
        match=match, side=tracker.models.ScoreEvent.Side.AWAY
    )
    latest_home = tracker.models.ScoreEvent.objects.create(
        match=match, side=tracker.models.ScoreEvent.Side.HOME
    )

    response = client_for(user).post(
        reverse("score-undo", args=[match.pk, tracker.models.ScoreEvent.Side.HOME]),
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert list(tracker.models.ScoreEvent.objects.all()) == [away, first_home]
    assert not tracker.models.ScoreEvent.objects.filter(pk=latest_home.pk).exists()
    assert response.context["home_score"] == 1
    assert response.context["away_score"] == 1


@pytest.mark.django_db
def test_match_delete_removes_owned_match(
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
    assert response["Location"] == reverse("match-list")
    assert not tracker.models.Match.objects.exists()
