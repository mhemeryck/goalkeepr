from django.urls import path

from tracker import views

urlpatterns = [
    path("", views.match_list, name="match-list"),
    path("teams/", views.team_list, name="team-list"),
    path("teams/add/", views.team_create, name="team-create"),
    path("teams/<int:pk>/", views.team_detail, name="team-detail"),
    path("teams/<int:pk>/edit/", views.team_edit, name="team-edit"),
    path("teams/<int:pk>/delete/", views.team_delete, name="team-delete"),
    path("teams/<int:team_pk>/seasons/add/", views.season_create, name="season-create"),
    path("seasons/<int:pk>/", views.season_detail, name="season-detail"),
    path("seasons/<int:pk>/edit/", views.season_edit, name="season-edit"),
    path("seasons/<int:pk>/delete/", views.season_delete, name="season-delete"),
    path(
        "seasons/<int:season_pk>/matches/add/", views.match_create, name="match-create"
    ),
    path("matches/<int:pk>/", views.match_detail, name="match-detail"),
    path("matches/<int:pk>/edit/", views.match_edit, name="match-edit"),
    path("matches/<int:pk>/delete/", views.match_delete, name="match-delete"),
    path("matches/<int:pk>/score/", views.match_score, name="match-score"),
    path("matches/<int:pk>/goal/<str:side>/", views.score_goal, name="score-goal"),
    path("matches/<int:pk>/undo/<str:side>/", views.score_undo, name="score-undo"),
]
