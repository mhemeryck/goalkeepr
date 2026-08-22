from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from goalkeepr import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("healthz/", views.healthz, name="healthz"),
    path("", include("tracker.urls")),
]
