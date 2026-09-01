import typing

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
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


class Season(models.Model):
    name = models.CharField(max_length=20, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ["-start_date", "-pk"]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        super().clean()
        if self.end_date < self.start_date:
            raise ValidationError({"end_date": "A season must end after it starts."})


class Team(models.Model):
    if typing.TYPE_CHECKING:
        home_matches: models.Manager[Match]
        away_matches: models.Manager[Match]
        memberships: models.Manager[TeamMembership]

    club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name="teams")
    season = models.ForeignKey(Season, on_delete=models.PROTECT, related_name="teams")
    age_group = models.CharField(max_length=20)
    designation = models.CharField(max_length=20, blank=True, default="")

    class Meta:
        ordering = ["club__name", "age_group", "designation", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["club", "season", "age_group", "designation"],
                name="unique_team_identity",
            )
        ]

    def __str__(self) -> str:
        suffix = " ".join(part for part in (self.age_group, self.designation) if part)
        return f"{self.club.name} {suffix}"


class Player(models.Model):
    if typing.TYPE_CHECKING:
        memberships: models.Manager[TeamMembership]

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
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
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


class UserPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="goalkeepr_preference",
    )
    default_team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        related_name="user_preferences",
        null=True,
        blank=True,
    )

    def __str__(self) -> str:
        return f"Preferences for {self.user}"

    def clean(self) -> None:
        super().clean()
        default_team = self.default_team
        if (
            default_team is not None
            and default_team.club.name.casefold()
            != settings.PRIMARY_CLUB_NAME.casefold()
        ):
            raise ValidationError(
                {"default_team": "The default team must belong to the primary club."}
            )


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


class ScoreEvent(models.Model):
    class Side(models.TextChoices):
        HOME = "home", gettext_lazy("Home")
        AWAY = "away", gettext_lazy("Away")

    match = models.ForeignKey(
        Match, on_delete=models.CASCADE, related_name="score_events"
    )
    side = models.CharField(max_length=4, choices=Side.choices)
    scorer = models.ForeignKey(
        Player,
        on_delete=models.SET_NULL,
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
