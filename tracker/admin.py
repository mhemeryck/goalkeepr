from django.contrib import admin

import tracker.models

admin.site.register(
    [
        tracker.models.Team,
        tracker.models.Club,
        tracker.models.Season,
        tracker.models.Player,
        tracker.models.TeamMembership,
        tracker.models.Match,
        tracker.models.ScoreEvent,
    ]
)
