from django.contrib import admin

import tracker.models

admin.site.register([tracker.models.Match, tracker.models.ScoreEvent])
