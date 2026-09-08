from collections import defaultdict

from django.db import migrations, models

AGE_GROUP_CHOICES = [(f"U{age}", f"U{age}") for age in range(6, 19)]
AGE_GROUP_VALUES = frozenset(value for value, _ in AGE_GROUP_CHOICES)


def normalize_age_groups(apps, schema_editor):
    team_model = apps.get_model("tracker", "Team")
    defaults_model = apps.get_model("tracker", "Defaults")
    teams_by_identity = defaultdict(list)

    for team in team_model.objects.all():
        age_group = team.age_group.upper()
        if age_group not in AGE_GROUP_VALUES:
            raise RuntimeError(
                f"Team {team.pk} has unsupported age group {team.age_group!r}. "
                "Change it to U6 through U18 before migrating."
            )
        teams_by_identity[(team.club_id, team.season, age_group)].append(team.pk)

    for identity, team_ids in teams_by_identity.items():
        if len(team_ids) > 1:
            raise RuntimeError(
                "Normalizing age groups would merge teams "
                f"{team_ids} with identity {identity!r}. Resolve the duplicates "
                "before migrating."
            )

    for team in team_model.objects.all():
        team.age_group = team.age_group.upper()
        team.save(update_fields=["age_group"])

    for defaults in defaults_model.objects.exclude(default_age_group=""):
        age_group = defaults.default_age_group.upper()
        if age_group not in AGE_GROUP_VALUES:
            raise RuntimeError(
                f"Defaults {defaults.pk} has unsupported age group "
                f"{defaults.default_age_group!r}. Change it to U6 through U18 "
                "before migrating."
            )
        defaults.default_age_group = age_group
        defaults.save(update_fields=["default_age_group"])


class Migration(migrations.Migration):
    dependencies = [
        ("tracker", "0007_replace_season_with_year_choices"),
    ]

    operations = [
        migrations.RunPython(normalize_age_groups, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="team",
            name="age_group",
            field=models.CharField(choices=AGE_GROUP_CHOICES, max_length=3),
        ),
        migrations.AlterField(
            model_name="defaults",
            name="default_age_group",
            field=models.CharField(blank=True, choices=AGE_GROUP_CHOICES, max_length=3),
        ),
    ]
