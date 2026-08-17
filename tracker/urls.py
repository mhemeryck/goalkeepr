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
    path(
        "matches/<int:pk>/goal/<score_side:side>/", views.score_goal, name="score-goal"
    ),
    path(
        "matches/<int:pk>/undo/<score_side:side>/", views.score_undo, name="score-undo"
    ),
]
