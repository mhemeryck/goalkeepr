from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import resolve, reverse

import tracker.models


def make_match(
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
    *,
    status: tracker.models.Match.Status = tracker.models.Match.Status.FINISHED,
    primary_is_home: bool = True,
) -> tracker.models.Match:
    return tracker.models.Match.objects.create(
        home_team=primary_team if primary_is_home else opponent_team,
        away_team=opponent_team if primary_is_home else primary_team,
        match_date=date(2026, 8, 16),
        status=status,
    )


@pytest.mark.django_db
def test_match_list_is_public_and_shows_compact_opponent_context(
    client: Client,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(primary_team, opponent_team)

    response = client.get(reverse("match-list"))

    assert response.status_code == 200
    assert opponent_team.club.name in response.text
    assert str(primary_team) not in response.text
    assert str(opponent_team) not in response.text
    assert "Home" in response.text
    assert reverse("match-detail", args=[match.pk]) in response.text
    assert reverse("match-create") not in response.text


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status",
    [
        tracker.models.Match.Status.SCHEDULED,
        tracker.models.Match.Status.LIVE,
        tracker.models.Match.Status.CANCELLED,
    ],
)
def test_unfinished_match_is_not_displayed_as_a_draw(
    client: Client,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
    status: tracker.models.Match.Status,
) -> None:
    make_match(primary_team, opponent_team, status=status)

    response = client.get(reverse("match-list"))

    if status == tracker.models.Match.Status.LIVE:
        assert "Score 0 to 0" in response.text
    else:
        assert "Score 0 to 0" not in response.text
    assert str(tracker.models.Match.Status(status).label) in response.text


@pytest.mark.django_db
def test_finished_match_score_is_derived_from_events(
    client: Client,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(primary_team, opponent_team)
    tracker.models.ScoreEvent.objects.bulk_create(
        [
            tracker.models.ScoreEvent(match=match, side="home"),
            tracker.models.ScoreEvent(match=match, side="home"),
            tracker.models.ScoreEvent(match=match, side="away"),
        ]
    )

    response = client.get(reverse("match-list"))

    listed_match = response.context["matches"][0]
    assert listed_match.home_score_value == 2
    assert listed_match.away_score_value == 1
    assert "Score 2 to 1" in response.text


@pytest.mark.django_db
def test_match_list_defaults_to_current_season(
    client: Client,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    current_match = make_match(primary_team, opponent_team)
    old_home = tracker.models.Team.objects.create(
        club=primary_team.club,
        season=tracker.models.Season.YEAR_2025,
        age_group="U10",
    )
    old_away = tracker.models.Team.objects.create(
        club=opponent_team.club,
        season=tracker.models.Season.YEAR_2025,
        age_group="U10",
    )
    old_match = tracker.models.Match.objects.create(
        home_team=old_home,
        away_team=old_away,
        match_date=date(2025, 8, 16),
        status=tracker.models.Match.Status.FINISHED,
    )
    other_age_club = tracker.models.Club.objects.create(name="City")
    other_age_team = tracker.models.Team.objects.create(
        club=other_age_club,
        season=primary_team.season,
        age_group="U12",
    )
    other_age_match = tracker.models.Match.objects.create(
        home_team=other_age_team,
        away_team=opponent_team,
        match_date=date(2026, 8, 17),
        status=tracker.models.Match.Status.FINISHED,
    )

    response = client.get(reverse("match-list"))
    all_response = client.get(reverse("match-list"), {"season": "all"})

    assert current_match in response.context["matches"]
    assert old_match not in response.context["matches"]
    assert other_age_match not in response.context["matches"]
    assert old_match in all_response.context["matches"]
    assert other_age_match in all_response.context["matches"]


@pytest.mark.django_db
def test_defaults_view_limits_teams_to_the_selected_season(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
) -> None:
    tracker.models.Team.objects.create(
        club=primary_team.club,
        season=tracker.models.Season.YEAR_2025,
        age_group="U10",
    )
    client.force_login(user)

    response = client.get(reverse("defaults-edit"))

    assert response.status_code == 200
    assert f">{primary_team.club}</option>" in response.text
    assert 'value="U11"' in response.text
    assert 'value="U10"' in response.text


@pytest.mark.django_db
def test_defaults_can_be_changed_as_club_season_and_age_group(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
) -> None:
    client.force_login(user)

    response = client.post(
        reverse("defaults-edit"),
        {
            "default_club": primary_team.club_id,
            "default_season": primary_team.season,
            "default_age_group": primary_team.age_group,
        },
    )

    defaults = tracker.models.Defaults.objects.get(pk=1)
    assert response.status_code == 302
    assert defaults.default_club == primary_team.club
    assert defaults.default_season == primary_team.season
    assert defaults.default_age_group == primary_team.age_group


@pytest.mark.django_db
def test_match_list_searches_clubs_age_groups_and_seasons(
    client: Client,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(primary_team, opponent_team)

    for query in ("United", "U11", "2026-2027"):
        response = client.get(reverse("match-list"), {"q": query})
        assert match in response.context["matches"]

    response = client.get(reverse("match-list"), {"q": "missing"})
    assert match not in response.context["matches"]


@pytest.mark.django_db
def test_match_list_uses_load_more_pagination(
    client: Client,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    for _ in range(21):
        make_match(primary_team, opponent_team)

    response = client.get(reverse("match-list"))
    next_response = client.get(
        reverse("match-list"),
        {"page": 2},
        HTTP_HX_REQUEST="true",
    )

    assert len(response.context["matches"]) == 20
    assert "Load more" in response.text
    assert len(next_response.context["matches"]) == 1
    assert next_response.templates[0].name == "tracker/partials/match_page.html"


@pytest.mark.django_db
def test_anonymous_match_detail_is_read_only_and_polls(
    client: Client,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(
        primary_team, opponent_team, status=tracker.models.Match.Status.LIVE
    )

    response = client.get(reverse("match-detail", args=[match.pk]))

    assert response.status_code == 200
    assert 'id="scoreboard"' in response.text
    assert 'hx-trigger="every 5s"' in response.text
    assert reverse("score-goal", args=[match.pk, "home"]) not in response.text
    assert reverse("match-delete", args=[match.pk]) not in response.text


@pytest.mark.django_db
def test_finished_match_detail_does_not_poll(
    client: Client,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(primary_team, opponent_team)

    response = client.get(reverse("match-detail", args=[match.pk]))

    assert 'hx-trigger="every 5s"' not in response.text


@pytest.mark.django_db
def test_authenticated_match_detail_has_lifecycle_controls(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(
        primary_team,
        opponent_team,
        status=tracker.models.Match.Status.SCHEDULED,
    )
    client.force_login(user)

    response = client.get(reverse("match-detail", args=[match.pk]))

    assert reverse("match-set-status", args=[match.pk, "live"]) in response.text
    assert reverse("match-set-status", args=[match.pk, "cancelled"]) in response.text
    assert reverse("match-set-status", args=[match.pk, "finished"]) not in response.text
    assert 'hx-trigger="every 5s"' not in response.text


@pytest.mark.django_db
def test_status_is_changed_explicitly(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(
        primary_team,
        opponent_team,
        status=tracker.models.Match.Status.SCHEDULED,
    )
    client.force_login(user)

    response = client.post(reverse("match-set-status", args=[match.pk, "live"]))

    match.refresh_from_db()
    assert response.status_code == 302
    assert match.status == tracker.models.Match.Status.LIVE


@pytest.mark.django_db
def test_invalid_status_transition_is_rejected(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(
        primary_team,
        opponent_team,
        status=tracker.models.Match.Status.SCHEDULED,
    )
    client.force_login(user)

    response = client.post(reverse("match-set-status", args=[match.pk, "finished"]))

    match.refresh_from_db()
    assert response.status_code == 409
    assert match.status == tracker.models.Match.Status.SCHEDULED


@pytest.mark.django_db
def test_finished_match_requires_explicit_correction_mode(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(primary_team, opponent_team)
    client.force_login(user)

    response = client.get(reverse("match-detail", args=[match.pk]))
    correction_response = client.get(
        reverse("match-detail", args=[match.pk]),
        {"correct": "1"},
    )

    goal_url = reverse("score-goal", args=[match.pk, "home"])
    assert goal_url not in response.text
    assert goal_url in correction_response.text


@pytest.mark.django_db
def test_scheduled_and_cancelled_matches_reject_scoring(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(
        primary_team,
        opponent_team,
        status=tracker.models.Match.Status.SCHEDULED,
    )
    client.force_login(user)

    scheduled_response = client.post(reverse("score-goal", args=[match.pk, "home"]))
    match.status = tracker.models.Match.Status.CANCELLED
    match.save(update_fields=["status"])
    cancelled_response = client.post(reverse("score-goal", args=[match.pk, "home"]))

    assert scheduled_response.status_code == 403
    assert cancelled_response.status_code == 403
    assert not tracker.models.ScoreEvent.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status", [tracker.models.Match.Status.LIVE, tracker.models.Match.Status.FINISHED]
)
def test_live_and_finished_matches_allow_score_corrections(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
    status: tracker.models.Match.Status,
) -> None:
    match = make_match(primary_team, opponent_team, status=status)
    client.force_login(user)

    response = client.post(
        reverse("score-goal", args=[match.pk, "home"]),
        {"correction": "1"} if status == tracker.models.Match.Status.FINISHED else {},
        HTTP_HX_REQUEST="true",
    )
    event = tracker.models.ScoreEvent.objects.get()

    assert response.status_code == 200
    assert event.recorded_at == event.occurred_at
    assert response.context["home_score"] == 1


@pytest.mark.django_db
def test_historical_goal_contributes_without_fabricated_occurrence_time(
    client: Client,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(primary_team, opponent_team)
    event = tracker.models.ScoreEvent.objects.create(match=match, side="home")

    response = client.get(reverse("match-detail", args=[match.pk]))

    assert response.context["home_score"] == 1
    assert event.recorded_at.strftime("%H:%M:%S") not in response.text


@pytest.mark.django_db
def test_add_player_creates_membership_and_selects_without_recording_goal(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(
        primary_team, opponent_team, status=tracker.models.Match.Status.LIVE
    )
    client.force_login(user)

    response = client.post(
        reverse("match-player-add", args=[match.pk]),
        {"name": "Alex"},
        HTTP_HX_REQUEST="true",
    )

    player = tracker.models.Player.objects.get(name="Alex")
    assert response.status_code == 200
    assert tracker.models.TeamMembership.objects.filter(
        player=player, team=primary_team
    ).exists()
    assert not tracker.models.ScoreEvent.objects.exists()
    assert f'value="{player.pk}" selected' in response.text


@pytest.mark.django_db
def test_goal_scorer_must_be_on_the_household_roster(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(
        primary_team, opponent_team, status=tracker.models.Match.Status.LIVE
    )
    player = tracker.models.Player.objects.create(name="Alex")
    client.force_login(user)

    response = client.post(
        reverse("score-goal", args=[match.pk, "home"]),
        {"scorer": player.pk},
    )

    assert response.status_code == 400
    assert not tracker.models.ScoreEvent.objects.exists()


@pytest.mark.django_db
def test_goal_can_select_a_player_from_the_household_roster(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(
        primary_team, opponent_team, status=tracker.models.Match.Status.LIVE
    )
    player = tracker.models.Player.objects.create(name="Alex")
    tracker.models.TeamMembership.objects.create(player=player, team=primary_team)
    client.force_login(user)

    response = client.post(
        reverse("score-goal", args=[match.pk, "home"]),
        {"scorer": player.pk},
    )

    assert response.status_code == 302
    assert tracker.models.ScoreEvent.objects.get().scorer == player


@pytest.mark.django_db
def test_opponent_goal_ignores_submitted_scorer(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(
        primary_team, opponent_team, status=tracker.models.Match.Status.LIVE
    )
    client.force_login(user)

    response = client.post(
        reverse("score-goal", args=[match.pk, "away"]),
        {"scorer": "999"},
    )

    assert response.status_code == 302
    assert tracker.models.ScoreEvent.objects.get().scorer is None
    assert not tracker.models.Player.objects.exists()


@pytest.mark.django_db
def test_scoreboard_only_offers_scorer_for_primary_club(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(
        primary_team, opponent_team, status=tracker.models.Match.Status.LIVE
    )
    client.force_login(user)

    response = client.get(reverse("match-detail", args=[match.pk]))

    assert 'id="scorer-home"' in response.text
    assert 'id="scorer-away"' not in response.text
    assert response.text.count('hx-disabled-elt="find button"') == 4


@pytest.mark.django_db
def test_player_with_score_events_cannot_be_deleted(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(primary_team, opponent_team)
    player = tracker.models.Player.objects.create(name="Alex")
    tracker.models.ScoreEvent.objects.create(
        match=match,
        side=tracker.models.ScoreEvent.Side.HOME,
        scorer=player,
    )
    client.force_login(user)

    response = client.post(reverse("player-delete", args=[player.pk]))

    assert response.status_code == 302
    assert tracker.models.Player.objects.filter(pk=player.pk).exists()
    assert tracker.models.ScoreEvent.objects.get().scorer == player


@pytest.mark.django_db
def test_match_team_cannot_change_when_it_would_invalidate_a_scorer(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(primary_team, opponent_team)
    player = tracker.models.Player.objects.create(name="Alex")
    tracker.models.TeamMembership.objects.create(player=player, team=primary_team)
    tracker.models.ScoreEvent.objects.create(
        match=match,
        side=tracker.models.ScoreEvent.Side.HOME,
        scorer=player,
    )
    replacement_club = tracker.models.Club.objects.create(name="City")
    replacement_team = tracker.models.Team.objects.create(
        club=replacement_club,
        season=primary_team.season,
        age_group="U11",
    )
    client.force_login(user)

    response = client.post(
        reverse("match-field-edit", args=[match.pk, "home-team"]),
        {"home_team": replacement_team.pk},
    )

    match.refresh_from_db()
    assert response.status_code == 400
    assert match.home_team == primary_team
    assert "scorer attribution" in response.text


@pytest.mark.django_db
def test_team_club_edit_reassigns_team_without_renaming_shared_club(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    client.force_login(user)

    response = client.post(
        reverse("team-edit", args=[opponent_team.pk]),
        {
            "club_name": primary_team.club.name,
            "season": primary_team.season,
            "age_group": "U10",
        },
    )

    opponent_team.refresh_from_db()
    primary_team.club.refresh_from_db()
    assert response.status_code == 302
    assert opponent_team.club == primary_team.club
    assert primary_team.club.name == "K.F.C. Sparta Kolmont"


@pytest.mark.django_db
def test_club_edit_renames_the_club_without_changing_its_teams(
    client: Client,
    user: User,
    opponent_team: tracker.models.Team,
) -> None:
    client.force_login(user)

    response = client.post(
        reverse("club-edit", args=[opponent_team.club_id]),
        {"name": "United FC"},
    )

    opponent_team.refresh_from_db()
    assert response.status_code == 302
    assert opponent_team.club.name == "United FC"


@pytest.mark.django_db
def test_club_creation_and_safe_deletion(client: Client, user: User) -> None:
    client.force_login(user)

    create_response = client.post(reverse("club-create"), {"name": "New United"})
    club = tracker.models.Club.objects.get(name="New United")
    delete_response = client.post(reverse("club-delete", args=[club.pk]))

    assert create_response.status_code == 302
    assert delete_response.status_code == 302
    assert not tracker.models.Club.objects.filter(pk=club.pk).exists()


@pytest.mark.django_db
def test_club_with_teams_cannot_be_deleted(
    client: Client,
    user: User,
    opponent_team: tracker.models.Team,
) -> None:
    client.force_login(user)

    response = client.post(reverse("club-delete", args=[opponent_team.club_id]))

    assert response.status_code == 409
    assert "has teams" in response.text
    assert tracker.models.Club.objects.filter(pk=opponent_team.club_id).exists()


@pytest.mark.django_db
def test_season_fields_offer_the_fixed_year_range(client: Client, user: User) -> None:
    client.force_login(user)

    response = client.get(reverse("team-create"))

    assert '<option value="2015">2015-2016</option>' in response.text
    assert '<option value="2033">2033-2034</option>' in response.text


@pytest.mark.django_db
def test_match_creation_defaults_to_opponent_and_home_away_flow(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
) -> None:
    client.force_login(user)

    response = client.get(reverse("match-create"))

    assert response.status_code == 200
    assert 'name="opponent_team"' in response.text
    assert 'name="is_home"' in response.text
    assert 'name="home_team"' not in response.text
    assert 'name="away_team"' not in response.text
    assert 'name="status"' not in response.text


@pytest.mark.django_db
def test_match_opponents_are_filtered_by_defaults_with_an_override(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    other_team = tracker.models.Team.objects.create(
        club=opponent_team.club,
        season=opponent_team.season,
        age_group="U12",
    )
    client.force_login(user)

    response = client.get(reverse("match-create"))
    override_response = client.get(reverse("match-create"), {"all_teams": "1"})

    assert f'value="{opponent_team.pk}"' in response.text
    assert f'value="{other_team.pk}"' not in response.text
    assert f'value="{other_team.pk}"' in override_response.text


@pytest.mark.django_db
def test_match_creation_links_to_defaults_when_not_configured(
    client: Client,
    user: User,
) -> None:
    tracker.models.Defaults.objects.all().delete()
    client.force_login(user)

    response = client.get(reverse("match-create"))

    assert response.status_code == 409
    assert reverse("defaults-edit") in response.text


@pytest.mark.django_db
def test_match_creation_persists_explicit_participants(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    client.force_login(user)

    response = client.post(
        reverse("match-create"),
        {
            "opponent_team": opponent_team.pk,
            "is_home": "true",
            "match_date": "2026-08-16",
            "notes": "Cup match",
        },
    )

    match = tracker.models.Match.objects.get()
    assert response.status_code == 302
    assert match.home_team == primary_team
    assert match.away_team == opponent_team
    assert match.status == tracker.models.Match.Status.SCHEDULED


@pytest.mark.django_db
def test_match_creation_can_add_an_opponent_before_selecting_it(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
) -> None:
    client.force_login(user)

    response = client.post(
        f"{reverse('team-create')}?next=match-create",
        {
            "club_name": "New United",
            "season": primary_team.season,
            "age_group": primary_team.age_group,
        },
    )

    team = tracker.models.Team.objects.get(club__name="New United")
    assert response.status_code == 302
    assert response["Location"] == f"{reverse('match-create')}?opponent={team.pk}"
    assert team.season == primary_team.season
    assert team.age_group == primary_team.age_group


@pytest.mark.django_db
def test_team_creation_uses_editable_defaults(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
) -> None:
    client.force_login(user)

    response = client.get(reverse("team-create"))

    assert response.status_code == 200
    assert f'value="{primary_team.club.name}"' in response.text
    assert f'value="{primary_team.season}" selected' in response.text
    assert f'value="{primary_team.age_group}"' in response.text


@pytest.mark.django_db
def test_application_forms_do_not_render_generic_empty_options(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(primary_team, opponent_team)
    client.force_login(user)

    responses = [
        client.get(reverse("defaults-edit")),
        client.get(reverse("team-create")),
        client.get(reverse("match-create")),
        client.get(reverse("match-detail", args=[match.pk]), {"edit": "home-team"}),
    ]

    assert all("---------" not in response.text for response in responses)


@pytest.mark.django_db
def test_age_group_fields_offer_the_fixed_range(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    client.force_login(user)

    team_response = client.get(reverse("team-edit", args=[primary_team.pk]))
    defaults_response = client.get(reverse("defaults-edit"))

    assert team_response.status_code == 200
    assert '<select name="age_group"' in team_response.text
    assert '<option value="U6">U6</option>' in team_response.text
    assert '<option value="U18">U18</option>' in team_response.text
    assert 'list="age-groups"' not in team_response.text
    assert '<select name="default_age_group"' in defaults_response.text


@pytest.mark.django_db
def test_swap_teams_preserves_team_scores(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(primary_team, opponent_team)
    event = tracker.models.ScoreEvent.objects.create(match=match, side="home")
    client.force_login(user)

    response = client.post(reverse("match-swap-teams", args=[match.pk]))

    match.refresh_from_db()
    event.refresh_from_db()
    assert response.status_code == 302
    assert match.home_team == opponent_team
    assert match.away_team == primary_team
    assert event.side == tracker.models.ScoreEvent.Side.AWAY


@pytest.mark.django_db
def test_team_statistics_only_include_finished_matches(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    finished = make_match(primary_team, opponent_team)
    tracker.models.ScoreEvent.objects.create(match=finished, side="home")
    make_match(
        primary_team,
        opponent_team,
        status=tracker.models.Match.Status.SCHEDULED,
    )
    client.force_login(user)

    response = client.get(reverse("team-list"))
    opponent_result = next(
        result
        for result in response.context["teams"]
        if result["team"] == opponent_team
    )

    assert opponent_result["wins"] == 0
    assert opponent_result["draws"] == 0
    assert opponent_result["losses"] == 1
    assert opponent_result["match_count"] == 2


@pytest.mark.django_db
def test_club_pages_group_seasonal_teams(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
) -> None:
    client.force_login(user)

    list_response = client.get(reverse("club-list"))
    detail_response = client.get(reverse("club-detail", args=[primary_team.club_id]))

    assert list_response.status_code == 200
    assert primary_team.club.name in list_response.text
    assert reverse("club-detail", args=[primary_team.club_id]) in list_response.text
    assert detail_response.status_code == 200
    assert primary_team.get_season_display() in detail_response.text
    assert reverse("team-detail", args=[primary_team.pk]) in detail_response.text


@pytest.mark.django_db
def test_team_detail_shows_roster_and_matches(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(primary_team, opponent_team)
    player = tracker.models.Player.objects.create(name="Alex")
    tracker.models.TeamMembership.objects.create(player=player, team=primary_team)
    client.force_login(user)

    response = client.get(reverse("team-detail", args=[primary_team.pk]))

    assert response.status_code == 200
    assert player.name in response.text
    assert reverse("player-detail", args=[player.pk]) in response.text
    assert reverse("match-detail", args=[match.pk]) in response.text


@pytest.mark.django_db
def test_player_detail_shows_memberships_and_goals(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(primary_team, opponent_team)
    player = tracker.models.Player.objects.create(name="Alex")
    tracker.models.TeamMembership.objects.create(player=player, team=primary_team)
    tracker.models.ScoreEvent.objects.create(
        match=match,
        side=tracker.models.ScoreEvent.Side.HOME,
        scorer=player,
    )
    client.force_login(user)

    response = client.get(reverse("player-detail", args=[player.pk]))

    assert response.status_code == 200
    assert str(primary_team) in response.text
    assert primary_team.get_season_display() in response.text
    assert reverse("team-detail", args=[primary_team.pk]) in response.text
    assert reverse("match-detail", args=[match.pk]) in response.text


@pytest.mark.django_db
def test_match_writes_require_login(
    client: Client,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(primary_team, opponent_team)

    response = client.post(reverse("score-goal", args=[match.pk, "home"]))

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("login"))


def test_score_side_url_is_converted_to_enum() -> None:
    match = resolve("/matches/1/goal/home/")

    assert match.kwargs["side"] is tracker.models.ScoreEvent.Side.HOME
