from django.urls import path, register_converter

from tracker import converters, views

register_converter(converters.ScoreSideConverter, "score_side")

urlpatterns = [
    path("", views.match_list, name="match-list"),
    path("matches/fragment/", views.match_list_fragment, name="match-list-fragment"),
    path("matches/add/", views.match_create, name="match-create"),
    path("matches/<int:pk>/", views.match_detail, name="match-detail"),
    path("matches/<int:pk>/edit/", views.match_edit, name="match-edit"),
    path("matches/<int:pk>/delete/", views.match_delete, name="match-delete"),
    path("matches/<int:pk>/score/", views.match_score, name="match-score"),
    path("players/", views.player_list, name="player-list"),
    path("players/<int:pk>/edit/", views.player_edit, name="player-edit"),
    path("players/<int:pk>/delete/", views.player_delete, name="player-delete"),
    path("teams/", views.team_list, name="team-list"),
    path("teams/<int:pk>/edit/", views.team_edit, name="team-edit"),
    path("teams/<int:pk>/delete/", views.team_delete, name="team-delete"),
    path(
        "matches/<int:pk>/goal/<score_side:side>/", views.score_goal, name="score-goal"
    ),
    path(
        "matches/<int:pk>/undo/<score_side:side>/", views.score_undo, name="score-undo"
    ),
]
