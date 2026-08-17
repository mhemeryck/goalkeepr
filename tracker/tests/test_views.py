from datetime import date

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, override_settings
from django.urls import resolve, reverse

import tracker.models


def make_match(
    *,
    opponent_name: str = "United",
    is_home: bool = True,
) -> tracker.models.Match:
    return tracker.models.Match.objects.create(
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
    first = make_match()
    second = make_match(opponent_name="City")

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
    match = make_match()
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
@pytest.mark.parametrize("authenticated", [False, True])
def test_match_list_polls_for_updates(
    client: Client,
    user: User,
    authenticated: bool,
) -> None:
    if authenticated:
        client.force_login(user)

    response = client.get(reverse("match-list"))

    assert f'hx-get="{reverse("match-list-fragment")}"' in response.text
    assert 'hx-trigger="every 5s"' in response.text


@pytest.mark.django_db
def test_match_list_fragment_is_public_and_returns_updated_scores(
    client: Client,
) -> None:
    match = make_match()

    initial_response = client.get(reverse("match-list-fragment"))
    tracker.models.ScoreEvent.objects.create(
        match=match,
        side=tracker.models.ScoreEvent.Side.HOME,
    )
    updated_response = client.get(reverse("match-list-fragment"))

    assert initial_response.status_code == 200
    assert 'aria-label="Score 0 to 0"' in initial_response.text
    assert updated_response.status_code == 200
    assert 'aria-label="Score 1 to 0"' in updated_response.text


@pytest.mark.django_db
def test_match_detail_is_public_and_read_only(client: Client, user: User) -> None:
    match = make_match()

    response = client.get(reverse("match-detail", args=[match.pk]))

    assert response.status_code == 200
    assert reverse("match-edit", args=[match.pk]) not in response.text
    assert reverse("match-delete", args=[match.pk]) not in response.text
    assert reverse("match-score", args=[match.pk]) not in response.text


@pytest.mark.django_db
def test_missing_match_uses_styled_not_found_page(client: Client) -> None:
    response = client.get(reverse("match-detail", args=[999]))

    assert response.status_code == 404
    assert [template.name for template in response.templates] == [
        "404.html",
        "base.html",
    ]
    assert "Wide of the post" in response.text
    assert reverse("match-list") in response.text


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
    match = make_match(is_home=is_home)

    response = client.get(reverse("match-detail", args=[match.pk]))

    assert heading in response.text


@pytest.mark.django_db
def test_authenticated_user_sees_match_write_actions(
    user: User,
    client: Client,
) -> None:
    match = make_match()
    client.force_login(user)

    response = client.get(reverse("match-detail", args=[match.pk]))

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
    client: Client,
) -> None:
    client.force_login(user)

    response = client.get(reverse("match-create"))

    assert response.status_code == 200
    assert response.context["form"]["is_home"].value() is True
    assert "location" not in response.context["form"].fields


@pytest.mark.django_db
def test_match_create_defaults_date_to_today(
    user: User,
    client: Client,
) -> None:
    client.force_login(user)

    response = client.get(reverse("match-create"))

    assert response.status_code == 200
    assert response.context["form"]["match_date"].value() == date.today()


@pytest.mark.django_db
def test_match_create_keeps_notes_collapsed_by_default(
    user: User,
    client: Client,
) -> None:
    client.force_login(user)

    response = client.get(reverse("match-create"))

    assert response.status_code == 200
    assert "<details>" in response.text
    assert "<summary>Notes</summary>" in response.text


@pytest.mark.django_db
def test_match_create_persists_match(
    user: User,
    client: Client,
) -> None:
    client.force_login(user)

    response = client.post(
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
    assert match.opponent_name == "United"


@pytest.mark.django_db
def test_match_edit_populates_date_field(
    user: User,
    client: Client,
) -> None:
    match = make_match()
    client.force_login(user)

    response = client.get(reverse("match-edit", args=[match.pk]))

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
    match = make_match()
    url = reverse(route_name, args=(match.pk, *args))

    response = getattr(client, method)(url)

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("login"))


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("route_name", "method", "args", "expected_status"),
    [
        ("match-edit", "get", (), 200),
        ("match-delete", "post", (), 302),
        ("match-score", "get", (), 200),
        ("score-goal", "post", (tracker.models.ScoreEvent.Side.HOME,), 200),
        ("score-undo", "post", (tracker.models.ScoreEvent.Side.HOME,), 200),
    ],
)
def test_match_writes_allow_another_user(
    other_user: User,
    client: Client,
    route_name: str,
    method: str,
    args: tuple[str, ...],
    expected_status: int,
) -> None:
    match = make_match()
    url = reverse(route_name, args=(match.pk, *args))
    client.force_login(other_user)

    response = getattr(client, method)(url)

    assert response.status_code == expected_status


@pytest.mark.django_db
def test_goal_records_event_and_returns_score_fragment(
    user: User,
    client: Client,
) -> None:
    match = make_match()
    client.force_login(user)

    response = client.post(
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


def test_score_side_url_is_converted_to_enum() -> None:
    match = resolve("/matches/1/goal/home/")

    assert match.kwargs["side"] is tracker.models.ScoreEvent.Side.HOME


@pytest.mark.django_db
def test_goal_rejects_invalid_side(
    user: User,
    client: Client,
) -> None:
    match = make_match()
    client.force_login(user)

    response = client.post(f"/matches/{match.pk}/goal/invalid/")

    assert response.status_code == 404
    assert not tracker.models.ScoreEvent.objects.exists()


@pytest.mark.django_db
def test_undo_removes_most_recent_event_for_selected_side(
    user: User,
    client: Client,
) -> None:
    match = make_match()
    first_home = tracker.models.ScoreEvent.objects.create(
        match=match, side=tracker.models.ScoreEvent.Side.HOME
    )
    away = tracker.models.ScoreEvent.objects.create(
        match=match, side=tracker.models.ScoreEvent.Side.AWAY
    )
    latest_home = tracker.models.ScoreEvent.objects.create(
        match=match, side=tracker.models.ScoreEvent.Side.HOME
    )
    client.force_login(user)

    response = client.post(
        reverse("score-undo", args=[match.pk, tracker.models.ScoreEvent.Side.HOME]),
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert list(tracker.models.ScoreEvent.objects.all()) == [away, first_home]
    assert not tracker.models.ScoreEvent.objects.filter(pk=latest_home.pk).exists()
    assert response.context["home_score"] == 1
    assert response.context["away_score"] == 1


@pytest.mark.django_db
def test_match_delete_removes_match(
    user: User,
    client: Client,
) -> None:
    match = make_match()
    client.force_login(user)
    url = reverse("match-delete", args=[match.pk])

    confirmation = client.get(url)
    response = client.post(url)

    assert confirmation.status_code == 200
    assert response.status_code == 302
    assert response["Location"] == reverse("match-list")
    assert not tracker.models.Match.objects.exists()
