from __future__ import annotations

import typing

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy


class Match(models.Model):
    if typing.TYPE_CHECKING:
        score_events: models.Manager[ScoreEvent]

    opponent_name = models.CharField(max_length=100)
    match_date = models.DateField()
    is_home = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-match_date", "-pk"]

    def __str__(self) -> str:
        return f"Match against {self.opponent_name} on {self.match_date}"


class ScoreEvent(models.Model):
    class Side(models.TextChoices):
        HOME = "home", gettext_lazy("Home")
        AWAY = "away", gettext_lazy("Away")

    match = models.ForeignKey(
        Match, on_delete=models.CASCADE, related_name="score_events"
    )
    side = models.CharField(max_length=4, choices=Side.choices)
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-recorded_at", "-pk"]

    def __str__(self) -> str:
        return f"{self.Side(self.side).label} goal at {self.recorded_at}"
