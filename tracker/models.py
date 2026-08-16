from django.conf import settings
from django.db import models
from django.utils import timezone


class Team(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teams",
    )
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"], name="unique_team_name_per_owner"
            )
        ]

    def __str__(self) -> str:
        return self.name


class Season(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="seasons")
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-name"]
        constraints = [
            models.UniqueConstraint(
                fields=["team", "name"], name="unique_season_name_per_team"
            )
        ]

    def __str__(self) -> str:
        return f"{self.team}: {self.name}"


class Match(models.Model):
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="matches")
    opponent_name = models.CharField(max_length=100)
    match_date = models.DateField()
    is_home = models.BooleanField(default=True)
    location = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-match_date", "-pk"]

    def __str__(self) -> str:
        return f"{self.season.team} v {self.opponent_name}"

    @property
    def home_name(self) -> str:
        return self.season.team.name if self.is_home else self.opponent_name

    @property
    def away_name(self) -> str:
        return self.opponent_name if self.is_home else self.season.team.name

    @property
    def home_score(self) -> int:
        return self.score_events.filter(side=ScoreEvent.Side.HOME).count()

    @property
    def away_score(self) -> int:
        return self.score_events.filter(side=ScoreEvent.Side.AWAY).count()


class ScoreEvent(models.Model):
    class Side(models.TextChoices):
        HOME = "home", "Home"
        AWAY = "away", "Away"

    match = models.ForeignKey(
        Match, on_delete=models.CASCADE, related_name="score_events"
    )
    side = models.CharField(max_length=4, choices=Side.choices)
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-recorded_at", "-pk"]

    def __str__(self) -> str:
        return f"{self.get_side_display()} goal at {self.recorded_at}"
