import datetime

import django.db.models.deletion
from django.db import migrations, models

SEASON_CHOICES = [(year, f"{year}-{year + 1}") for year in range(2015, 2034)]


def copy_season_years(apps, schema_editor):
    team_model = apps.get_model("tracker", "Team")
    defaults_model = apps.get_model("tracker", "Defaults")

    for team in team_model.objects.select_related("season"):
        team.season_year = team.season.start_date.year
        team.save(update_fields=["season_year"])

    for defaults in defaults_model.objects.select_related("default_season"):
        if defaults.default_season_id is not None:
            defaults.default_season_year = defaults.default_season.start_date.year
            defaults.save(update_fields=["default_season_year"])


def restore_seasons(apps, schema_editor):
    season_model = apps.get_model("tracker", "Season")
    team_model = apps.get_model("tracker", "Team")
    defaults_model = apps.get_model("tracker", "Defaults")
    years = set(team_model.objects.values_list("season_year", flat=True))
    years.update(
        defaults_model.objects.exclude(default_season_year=None).values_list(
            "default_season_year", flat=True
        )
    )

    for year in years:
        season = season_model.objects.create(
            name=f"{year}-{year + 1}",
            start_date=datetime.date(year, 7, 1),
            end_date=datetime.date(year + 1, 6, 30),
        )
        team_model.objects.filter(season_year=year).update(season_id=season.pk)
        defaults_model.objects.filter(default_season_year=year).update(
            default_season_id=season.pk
        )


class Migration(migrations.Migration):
    dependencies = [
        ("tracker", "0006_remove_defaults_default_team_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="team",
            name="season_year",
            field=models.PositiveSmallIntegerField(null=True),
        ),
        migrations.AddField(
            model_name="defaults",
            name="default_season_year",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="team",
            name="season",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="teams",
                to="tracker.season",
            ),
        ),
        migrations.AlterField(
            model_name="defaults",
            name="default_season",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="tracker.season",
            ),
        ),
        migrations.RunPython(copy_season_years, restore_seasons),
        migrations.RemoveConstraint(
            model_name="team",
            name="unique_team_identity",
        ),
        migrations.RemoveField(model_name="team", name="season"),
        migrations.RemoveField(model_name="defaults", name="default_season"),
        migrations.DeleteModel(name="Season"),
        migrations.RenameField(
            model_name="team", old_name="season_year", new_name="season"
        ),
        migrations.RenameField(
            model_name="defaults",
            old_name="default_season_year",
            new_name="default_season",
        ),
        migrations.AlterField(
            model_name="team",
            name="season",
            field=models.PositiveSmallIntegerField(choices=SEASON_CHOICES),
        ),
        migrations.AlterField(
            model_name="defaults",
            name="default_season",
            field=models.PositiveSmallIntegerField(
                blank=True, choices=SEASON_CHOICES, null=True
            ),
        ),
        migrations.AddConstraint(
            model_name="team",
            constraint=models.UniqueConstraint(
                fields=("club", "season", "age_group"),
                name="unique_team_identity",
            ),
        ),
    ]
