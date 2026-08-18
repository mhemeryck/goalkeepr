from datetime import date

import pytest
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
