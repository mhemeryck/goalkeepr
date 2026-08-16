from django.conf import settings
from django.db import models
from django.utils import timezone


class Match(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="matches",
    )
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
        return f"Match against {self.opponent_name} on {self.match_date}"


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
