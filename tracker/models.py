import typing

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy


class Team(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name", "pk"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="unique_team_name_case_insensitive",
            )
        ]

    def __str__(self) -> str:
        return self.name


class Player(models.Model):
    name = models.CharField(max_length=100)

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


class Match(models.Model):
    if typing.TYPE_CHECKING:
        score_events: models.Manager[ScoreEvent]

    opponent = models.ForeignKey(
        Team,
        on_delete=models.PROTECT,
        related_name="matches",
    )
    match_date = models.DateField()
    is_home = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-match_date", "-pk"]

    def __str__(self) -> str:
        return f"Match against {self.opponent.name} on {self.match_date}"


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

    class Meta:
        ordering = ["-recorded_at", "-pk"]

    def __str__(self) -> str:
        return f"{self.Side(self.side).label} goal at {self.recorded_at}"

    def clean(self) -> None:
        super().clean()
        if self.scorer_id is None or self.match_id is None:
            return
        household_side = self.Side.HOME if self.match.is_home else self.Side.AWAY
        if self.side != household_side:
            raise ValidationError(
                {"scorer": "A scorer can only be recorded for household-team goals."}
            )
