from django.urls import path

from tracker import views

urlpatterns = [
    path("", views.match_list, name="match-list"),
    path("matches/add/", views.match_create, name="match-create"),
    path("matches/<int:pk>/", views.match_detail, name="match-detail"),
    path("matches/<int:pk>/edit/", views.match_edit, name="match-edit"),
    path("matches/<int:pk>/delete/", views.match_delete, name="match-delete"),
    path("matches/<int:pk>/score/", views.match_score, name="match-score"),
    path("matches/<int:pk>/goal/<str:side>/", views.score_goal, name="score-goal"),
    path("matches/<int:pk>/undo/<str:side>/", views.score_undo, name="score-undo"),
]
