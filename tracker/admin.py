from django.contrib import admin

import tracker.models

admin.site.register(
    [
        tracker.models.Team,
        tracker.models.Player,
        tracker.models.Match,
        tracker.models.ScoreEvent,
    ]
)
