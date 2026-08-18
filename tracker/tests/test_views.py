from datetime import date, timedelta

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, override_settings
from django.urls import resolve, reverse
from django.utils import timezone

import tracker.models


def make_match(
    *,
    opponent_name: str = "United",
    is_home: bool = True,
    match_date: date = date(2026, 8, 16),
) -> tracker.models.Match:
    opponent, _ = tracker.models.Team.objects.get_or_create(name=opponent_name)
    return tracker.models.Match.objects.create(
        opponent=opponent,
        match_date=match_date,
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
    assert f'id="match-link-{match.pk}"' in initial_response.text
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
    assert match.opponent.name == "United"


@pytest.mark.django_db
def test_match_form_reuses_opponent_case_insensitively(
    user: User,
    client: Client,
) -> None:
    existing = tracker.models.Team.objects.create(name="United")
    client.force_login(user)

    response = client.post(
        reverse("match-create"),
        {
            "opponent_name": " united ",
            "match_date": "2026-08-16",
            "is_home": "True",
        },
    )

    assert response.status_code == 302
    assert tracker.models.Team.objects.count() == 1
    assert tracker.models.Match.objects.get().opponent == existing


@pytest.mark.django_db
def test_match_form_offers_existing_opponents(
    user: User,
    client: Client,
) -> None:
    tracker.models.Team.objects.create(name="City")
    client.force_login(user)

    response = client.get(reverse("match-create"))

    assert '<datalist id="opponent-teams">' in response.text
    assert '<option value="City">' in response.text


@pytest.mark.django_db
def test_creating_future_match_redirects_to_fixture_detail(
    user: User,
    client: Client,
) -> None:
    client.force_login(user)
    future_date = timezone.localdate() + timedelta(days=1)

    response = client.post(
        reverse("match-create"),
        {
            "opponent_name": "United",
            "match_date": future_date.isoformat(),
            "is_home": "True",
        },
    )

    match = tracker.models.Match.objects.get()
    assert response.status_code == 302
    assert response["Location"] == reverse("match-detail", args=[match.pk])


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


@pytest.mark.django_db
@pytest.mark.parametrize("is_home", [True, False])
def test_household_goal_can_record_optional_scorer(
    user: User,
    client: Client,
    is_home: bool,
) -> None:
    match = make_match(is_home=is_home)
    player = tracker.models.Player.objects.create(name="Alex")
    side = (
        tracker.models.ScoreEvent.Side.HOME
        if is_home
        else tracker.models.ScoreEvent.Side.AWAY
    )
    client.force_login(user)

    response = client.post(
        reverse("score-goal", args=[match.pk, side]),
        {"scorer_name": "Alex"},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert tracker.models.ScoreEvent.objects.get().scorer == player
    assert "Latest goals" in response.text
    assert "Alex" in response.text
    assert f"{reverse('player-list')}#player-{player.pk}" in response.text


@pytest.mark.django_db
def test_scoreboard_aligns_goal_controls_when_scorer_is_home_only(
    user: User,
    client: Client,
) -> None:
    match = make_match(is_home=True)
    client.force_login(user)

    response = client.get(reverse("match-score", args=[match.pk]))

    assert response.text.count('class="scorer-slot') == 2
    assert response.text.count("scorer-placeholder") == 1


@pytest.mark.django_db
def test_opponent_goal_ignores_submitted_scorer(
    user: User,
    client: Client,
) -> None:
    match = make_match(is_home=True)
    tracker.models.Player.objects.create(name="Alex")
    client.force_login(user)

    response = client.post(
        reverse(
            "score-goal",
            args=[match.pk, tracker.models.ScoreEvent.Side.AWAY],
        ),
        {"scorer_name": "Alex"},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert tracker.models.ScoreEvent.objects.get().scorer is None
    assert "Scorer not recorded" not in response.text


@pytest.mark.django_db
def test_public_scorer_name_links_only_when_authenticated(
    user: User,
    client: Client,
) -> None:
    match = make_match()
    player = tracker.models.Player.objects.create(name="Alex")
    tracker.models.ScoreEvent.objects.create(
        match=match,
        side=tracker.models.ScoreEvent.Side.HOME,
        scorer=player,
    )

    public_response = client.get(reverse("match-detail", args=[match.pk]))
    client.force_login(user)
    private_response = client.get(reverse("match-detail", args=[match.pk]))

    player_url = f"{reverse('player-list')}#player-{player.pk}"
    assert "by Alex" in public_response.text
    assert player_url not in public_response.text
    assert "by Alex" in private_response.text
    assert player_url in private_response.text


@pytest.mark.django_db
def test_scoreboard_shows_only_five_most_recent_goals(
    user: User,
    client: Client,
) -> None:
    match = make_match()
    players = [
        tracker.models.Player.objects.create(name=f"Player {number}")
        for number in range(6)
    ]
    for player in players:
        tracker.models.ScoreEvent.objects.create(
            match=match,
            side=tracker.models.ScoreEvent.Side.HOME,
            scorer=player,
        )
    client.force_login(user)

    response = client.get(reverse("match-score", args=[match.pk]))

    assert response.status_code == 200
    assert [event.scorer for event in response.context["recent_events"]] == list(
        reversed(players[1:])
    )
    marker = '<span class="goal-marker" aria-hidden="true"></span>'
    assert response.text.count(marker) == 5


@pytest.mark.django_db
def test_player_management_requires_login(client: Client) -> None:
    response = client.get(reverse("player-list"))

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("login"))


@pytest.mark.django_db
def test_player_list_shows_inline_edit_and_total_goals(
    user: User,
    client: Client,
) -> None:
    player = tracker.models.Player.objects.create(name="Alxe")
    match = make_match()
    tracker.models.ScoreEvent.objects.bulk_create(
        [
            tracker.models.ScoreEvent(
                match=match,
                side=tracker.models.ScoreEvent.Side.HOME,
                scorer=player,
            ),
            tracker.models.ScoreEvent(
                match=match,
                side=tracker.models.ScoreEvent.Side.HOME,
                scorer=player,
            ),
        ]
    )
    client.force_login(user)

    list_response = client.get(reverse("player-list"))

    assert 'id="player-' in list_response.text
    assert "2 goals" in list_response.text
    assert 'aria-label="Delete Alxe"' in list_response.text
    assert f'hx-get="{reverse("player-edit", args=[player.pk])}"' in list_response.text
    assert "Edit" not in list_response.text


@pytest.mark.django_db
def test_player_can_be_edited_from_player_list(user: User, client: Client) -> None:
    player = tracker.models.Player.objects.create(name="Alxe")
    client.force_login(user)

    edit_response = client.post(
        reverse("player-edit", args=[player.pk]),
        {"name": "Alex"},
    )

    player.refresh_from_db()
    assert edit_response.status_code == 302
    assert edit_response["Location"] == reverse("player-list")
    assert player.name == "Alex"


@pytest.mark.django_db
def test_clicking_player_returns_inline_textbox(user: User, client: Client) -> None:
    player = tracker.models.Player.objects.create(name="Alex")
    client.force_login(user)

    response = client.get(
        reverse("player-edit", args=[player.pk]),
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert response.templates[0].name == "tracker/partials/player_edit_row.html"
    assert 'value="Alex"' in response.text

    save_response = client.post(
        reverse("player-edit", args=[player.pk]),
        {"name": "Alexandra"},
        HTTP_HX_REQUEST="true",
    )

    assert save_response.status_code == 200
    assert save_response.templates[0].name == "tracker/partials/player_row.html"
    assert "Alexandra" in save_response.text
    assert 'name="name"' not in save_response.text


@pytest.mark.django_db
def test_inline_player_edit_shows_duplicate_name_error(
    user: User,
    client: Client,
) -> None:
    tracker.models.Player.objects.create(name="Alex")
    player = tracker.models.Player.objects.create(name="Sam")
    client.force_login(user)

    response = client.post(
        reverse("player-edit", args=[player.pk]),
        {"name": "alex"},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert response.templates[0].name == "tracker/partials/player_edit_row.html"
    assert "Constraint" in response.text
    assert tracker.models.Player.objects.filter(name="Sam").exists()


@pytest.mark.django_db
def test_deleting_player_keeps_goal_without_scorer(
    user: User,
    client: Client,
) -> None:
    match = make_match()
    player = tracker.models.Player.objects.create(name="Wrong name")
    event = tracker.models.ScoreEvent.objects.create(
        match=match,
        side=tracker.models.ScoreEvent.Side.HOME,
        scorer=player,
    )
    client.force_login(user)

    response = client.post(reverse("player-delete", args=[player.pk]))

    event.refresh_from_db()
    assert response.status_code == 302
    assert response["Location"] == reverse("player-list")
    assert not tracker.models.Player.objects.exists()
    assert event.scorer is None


@pytest.mark.django_db
def test_future_fixture_hides_score_and_blocks_score_writes(
    user: User,
    client: Client,
) -> None:
    match = make_match(match_date=timezone.localdate() + timedelta(days=1))
    client.force_login(user)

    list_response = client.get(reverse("match-list"))
    detail_response = client.get(reverse("match-detail", args=[match.pk]))
    score_response = client.get(reverse("match-score", args=[match.pk]))
    goal_response = client.post(
        reverse(
            "score-goal",
            args=[match.pk, tracker.models.ScoreEvent.Side.HOME],
        )
    )

    assert "Fixture" in list_response.text
    assert "Score 0 to 0" not in list_response.text
    assert " v United" in detail_response.text
    assert reverse("match-score", args=[match.pk]) not in detail_response.text
    assert score_response.status_code == 302
    assert score_response["Location"] == reverse("match-detail", args=[match.pk])
    assert goal_response.status_code == 403
    assert not tracker.models.ScoreEvent.objects.exists()


@pytest.mark.django_db
def test_match_on_today_is_scoreable(user: User, client: Client) -> None:
    match = make_match(match_date=timezone.localdate())
    client.force_login(user)

    response = client.post(
        reverse(
            "score-goal",
            args=[match.pk, tracker.models.ScoreEvent.Side.HOME],
        ),
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert tracker.models.ScoreEvent.objects.filter(match=match).count() == 1


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
