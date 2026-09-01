from datetime import date

import pytest
from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_opponent_names_migrate_to_case_insensitive_teams() -> None:
    executor = MigrationExecutor(connection)
    executor.migrate([("tracker", "0002_remove_match_owner")])
    old_apps = executor.loader.project_state(
        [("tracker", "0002_remove_match_owner")]
    ).apps
    old_match = old_apps.get_model("tracker", "Match")
    old_match.objects.create(
        opponent_name="United",
        match_date=date(2026, 8, 16),
    )
    old_match.objects.create(
        opponent_name="united",
        match_date=date(2026, 8, 17),
    )

    executor = MigrationExecutor(connection)
    executor.migrate([("tracker", "0003_match_enhancements")])
    new_apps = executor.loader.project_state(
        [("tracker", "0003_match_enhancements")]
    ).apps
    team = new_apps.get_model("tracker", "Team")
    match = new_apps.get_model("tracker", "Match")

    assert team.objects.count() == 1
    assert {item.opponent_id for item in match.objects.all()} == {team.objects.get().pk}

    executor = MigrationExecutor(connection)
    executor.migrate([("tracker", "0002_remove_match_owner")])
    restored_apps = executor.loader.project_state(
        [("tracker", "0002_remove_match_owner")]
    ).apps
    restored_match = restored_apps.get_model("tracker", "Match")

    restored_names = set(restored_match.objects.values_list("opponent_name", flat=True))
    assert len(restored_names) == 1
    assert restored_names.pop().casefold() == "united"

    MigrationExecutor(connection).migrate([("tracker", "0003_match_enhancements")])


@pytest.mark.django_db(transaction=True)
def test_current_data_migrates_to_u11_club_team_domain() -> None:
    executor = MigrationExecutor(connection)
    executor.migrate([("tracker", "0003_match_enhancements")])
    old_apps = executor.loader.project_state(
        [("tracker", "0003_match_enhancements")]
    ).apps
    old_team = old_apps.get_model("tracker", "Team")
    old_match = old_apps.get_model("tracker", "Match")
    old_player = old_apps.get_model("tracker", "Player")
    old_event = old_apps.get_model("tracker", "ScoreEvent")
    opponent = old_team.objects.create(name="United")
    player = old_player.objects.create(name="Alex")
    finished_match = old_match.objects.create(
        opponent=opponent,
        match_date=date(2026, 8, 16),
        is_home=False,
        notes="Preserved",
    )
    event = old_event.objects.create(
        match=finished_match,
        side="away",
        scorer=player,
    )
    scheduled_match = old_match.objects.create(
        opponent=opponent,
        match_date=date(2027, 5, 1),
    )

    executor = MigrationExecutor(connection)
    executor.migrate([("tracker", "0004_expand_match_domain")])
    apps = executor.loader.project_state([("tracker", "0004_expand_match_domain")]).apps
    club = apps.get_model("tracker", "Club")
    season = apps.get_model("tracker", "Season")
    team = apps.get_model("tracker", "Team")
    match = apps.get_model("tracker", "Match")
    score_event = apps.get_model("tracker", "ScoreEvent")
    membership = apps.get_model("tracker", "TeamMembership")

    primary_club = club.objects.get(name=settings.PRIMARY_CLUB_NAME)
    primary_team = team.objects.get(club=primary_club)
    migrated_finished = match.objects.get(pk=finished_match.pk)
    migrated_scheduled = match.objects.get(pk=scheduled_match.pk)
    migrated_event = score_event.objects.get(pk=event.pk)

    assert season.objects.filter(
        name="2026-2027",
        start_date=date(2026, 7, 1),
        end_date=date(2027, 6, 30),
    ).exists()
    assert primary_team.age_group == "U11"
    assert migrated_finished.home_team.club.name == "United"
    assert migrated_finished.away_team == primary_team
    assert migrated_finished.status == "finished"
    assert migrated_finished.notes == "Preserved"
    assert migrated_scheduled.status == "scheduled"
    assert migrated_event.scorer.name == "Alex"
    assert migrated_event.occurred_at is None
    assert membership.objects.filter(player_id=player.pk, team=primary_team).exists()
    MigrationExecutor(connection).migrate([("tracker", "0004_expand_match_domain")])
