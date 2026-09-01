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
def test_match_list_is_public_and_shows_explicit_teams(
    client: Client,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(primary_team, opponent_team)

    response = client.get(reverse("match-list"))

    assert response.status_code == 200
    assert str(primary_team) in response.text
    assert str(opponent_team) in response.text
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
def test_anonymous_match_detail_is_read_only_and_polls(
    client: Client,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    match = make_match(primary_team, opponent_team)

    response = client.get(reverse("match-detail", args=[match.pk]))

    assert response.status_code == 200
    assert 'id="scoreboard"' in response.text
    assert 'hx-trigger="every 5s"' in response.text
    assert reverse("score-goal", args=[match.pk, "home"]) not in response.text
    assert reverse("match-delete", args=[match.pk]) not in response.text


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
    assert reverse("match-set-status", args=[match.pk, "finished"]) in response.text
    assert reverse("match-set-status", args=[match.pk, "cancelled"]) in response.text
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
def test_recording_scorer_creates_team_membership(
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
        reverse("score-goal", args=[match.pk, "home"]),
        {"scorer_name": "Alex"},
    )

    player = tracker.models.Player.objects.get(name="Alex")
    assert response.status_code == 302
    assert tracker.models.TeamMembership.objects.filter(
        player=player, team=primary_team
    ).exists()
    assert tracker.models.ScoreEvent.objects.get().scorer == player


@pytest.mark.django_db
def test_match_creation_leaves_both_teams_unselected(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
) -> None:
    client.force_login(user)

    response = client.get(reverse("match-create"))

    assert response.status_code == 200
    assert response.context["form"]["home_team"].value() is None
    assert response.context["form"]["away_team"].value() is None
    assert response.context["form"]["status"].value() == "scheduled"


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
            "home_team": primary_team.pk,
            "away_team": opponent_team.pk,
            "match_date": "2026-08-16",
            "status": "scheduled",
            "notes": "Cup match",
        },
    )

    match = tracker.models.Match.objects.get()
    assert response.status_code == 302
    assert match.home_team == primary_team
    assert match.away_team == opponent_team


@pytest.mark.django_db
def test_match_team_choices_prioritize_current_season(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
) -> None:
    previous_season = tracker.models.Season.objects.create(
        name="2025-2026",
        start_date=date(2025, 7, 1),
        end_date=date(2026, 6, 30),
    )
    previous_team = tracker.models.Team.objects.create(
        club=primary_team.club,
        season=previous_season,
        age_group="U10",
    )
    client.force_login(user)

    response = client.get(reverse("match-create"))
    choices = list(response.context["form"].fields["home_team"].choices)

    assert choices.index(
        (primary_team.pk, f"{primary_team} ({primary_team.season})")
    ) < choices.index((previous_team.pk, f"{previous_team} ({previous_team.season})"))


@pytest.mark.django_db
def test_team_age_group_field_offers_existing_values(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
    opponent_team: tracker.models.Team,
) -> None:
    opponent_team.age_group = "U10"
    opponent_team.save(update_fields=["age_group"])
    client.force_login(user)

    response = client.get(
        reverse("team-edit", args=[primary_team.pk]),
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert 'list="age-groups"' in response.text
    assert '<option value="U10">' in response.text
    assert '<option value="U11">' in response.text


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
