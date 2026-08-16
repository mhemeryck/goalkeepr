from django.contrib import admin

from tracker.models import Match, ScoreEvent, Season, Team

admin.site.register([Team, Season, Match, ScoreEvent])
