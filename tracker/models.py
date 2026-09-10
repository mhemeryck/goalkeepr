import typing
from datetime import date

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Lower
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext_lazy


class Club(models.Model):
    if typing.TYPE_CHECKING:
        teams: models.Manager[Team]

    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name", "pk"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="unique_club_name_case_insensitive",
            )
        ]

    def __str__(self) -> str:
        return self.name


class Season(models.IntegerChoices):
    YEAR_2022 = 2022, "2022-2023"
    YEAR_2023 = 2023, "2023-2024"
    YEAR_2024 = 2024, "2024-2025"
    YEAR_2025 = 2025, "2025-2026"
    YEAR_2026 = 2026, "2026-2027"
    YEAR_2027 = 2027, "2027-2028"
    YEAR_2028 = 2028, "2028-2029"
    YEAR_2029 = 2029, "2029-2030"
    YEAR_2030 = 2030, "2030-2031"
    YEAR_2031 = 2031, "2031-2032"
    YEAR_2032 = 2032, "2032-2033"
    YEAR_2033 = 2033, "2033-2034"

    @property
    def start_date(self) -> date:
        return date(self.value, 7, 1)

    @property
    def end_date(self) -> date:
        return date(self.value + 1, 6, 30)


class AgeGroup(models.TextChoices):
    U6 = "U6", "U6"
    U7 = "U7", "U7"
    U8 = "U8", "U8"
    U9 = "U9", "U9"
    U10 = "U10", "U10"
    U11 = "U11", "U11"
    U12 = "U12", "U12"
    U13 = "U13", "U13"
    U14 = "U14", "U14"
    U15 = "U15", "U15"
    U16 = "U16", "U16"
    U17 = "U17", "U17"
    U18 = "U18", "U18"


class Team(models.Model):
    if typing.TYPE_CHECKING:
        club_id: int
        home_matches: models.Manager[Match]
        away_matches: models.Manager[Match]
        memberships: models.Manager[TeamMembership]

    club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name="teams")
    season = models.PositiveSmallIntegerField(choices=Season.choices)
    age_group = models.CharField(max_length=3, choices=AgeGroup.choices)

    class Meta:
        ordering = ["club__name", "age_group", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["club", "season", "age_group"],
                name="unique_team_identity",
            )
        ]

    def __str__(self) -> str:
        return f"{self.club.name} {self.age_group}"


class Defaults(models.Model):
    default_club = models.ForeignKey(
        Club,
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    default_season = models.PositiveSmallIntegerField(
        choices=Season.choices,
        null=True,
        blank=True,
    )
    default_age_group = models.CharField(
        max_length=3,
        choices=AgeGroup.choices,
        blank=True,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(pk=1),
                name="single_defaults_record",
            )
        ]

    def __str__(self) -> str:
        return "Defaults"

    def clean(self) -> None:
        super().clean()
        default_club = self.default_club
        default_season = self.default_season
        if (
            default_club is not None
            and default_season is not None
            and self.default_age_group
            and not Team.objects.filter(
                club=default_club,
                season=default_season,
                age_group=self.default_age_group,
            ).exists()
        ):
            raise ValidationError(
                "The configured defaults must resolve to an existing team."
            )


@receiver(pre_delete, sender=Team)
def protect_default_team(
    sender: type[Team],
    instance: Team,
    using: str,
    **kwargs: typing.Any,
) -> None:
    del sender, kwargs
    if (
        Defaults.objects.using(using)
        .filter(
            default_club_id=instance.club_id,
            default_season=instance.season,
            default_age_group=instance.age_group,
        )
        .exists()
    ):
        raise ProtectedError(
            "The team is required by application defaults.",
            {instance},
        )


class Player(models.Model):
    if typing.TYPE_CHECKING:
        memberships: models.Manager[TeamMembership]
        score_events: models.Manager[ScoreEvent]

    name = models.CharField(max_length=100)
    teams = models.ManyToManyField(
        Team, through="TeamMembership", related_name="players"
    )

    class Meta:
        ordering = ["name", "pk"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="unique_player_name_case_insensitive",
            )
        ]

    def __str__(self) -> str:
        return self.name


class TeamMembership(models.Model):
    if typing.TYPE_CHECKING:
        player_id: int
        team_id: int

    player = models.ForeignKey(
        Player,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.PROTECT,
        related_name="memberships",
    )

    class Meta:
        ordering = ["team", "player"]
        constraints = [
            models.UniqueConstraint(
                fields=["player", "team"],
                name="unique_team_membership",
            )
        ]

    def __str__(self) -> str:
        return f"{self.player} in {self.team}"


class Match(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", gettext_lazy("Scheduled")
        LIVE = "live", gettext_lazy("Live")
        FINISHED = "finished", gettext_lazy("Finished")
        CANCELLED = "cancelled", gettext_lazy("Cancelled")

    if typing.TYPE_CHECKING:
        home_team_id: int
        away_team_id: int
        score_events: models.Manager[ScoreEvent]

    home_team = models.ForeignKey(
        Team,
        on_delete=models.PROTECT,
        related_name="home_matches",
    )
    away_team = models.ForeignKey(
        Team,
        on_delete=models.PROTECT,
        related_name="away_matches",
    )
    match_date = models.DateField()
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-match_date", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(home_team=models.F("away_team")),
                name="match_teams_must_differ",
            )
        ]

    def __str__(self) -> str:
        return f"{self.home_team} against {self.away_team} on {self.match_date}"

    def clean(self) -> None:
        super().clean()
        if self.home_team_id == self.away_team_id:
            raise ValidationError("Home and away teams must differ.")
        if (
            self.home_team_id is not None
            and self.away_team_id is not None
            and self.home_team.season != self.away_team.season
        ):
            raise ValidationError("Home and away teams must belong to the same season.")


class ScoreEvent(models.Model):
    class Side(models.TextChoices):
        HOME = "home", gettext_lazy("Home")
        AWAY = "away", gettext_lazy("Away")

    if typing.TYPE_CHECKING:
        match_id: int
        scorer_id: int | None

    match = models.ForeignKey(
        Match, on_delete=models.CASCADE, related_name="score_events"
    )
    side = models.CharField(max_length=4, choices=Side.choices)
    scorer = models.ForeignKey(
        Player,
        on_delete=models.PROTECT,
        related_name="score_events",
        null=True,
        blank=True,
    )
    recorded_at = models.DateTimeField(default=timezone.now)
    occurred_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-recorded_at", "-pk"]

    def __str__(self) -> str:
        return f"{self.Side(self.side).label} goal at {self.recorded_at}"

    def clean(self) -> None:
        super().clean()
        if self.scorer_id is None or self.match_id is None:
            return
        scoring_team_id = (
            self.match.home_team_id
            if self.side == self.Side.HOME
            else self.match.away_team_id
        )
        if not TeamMembership.objects.filter(
            player_id=self.scorer_id,
            team_id=scoring_team_id,
        ).exists():
            raise ValidationError(
                {"scorer": "The scorer must belong to the scoring team."}
            )
