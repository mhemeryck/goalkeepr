from django.conf import settings
from django.http import HttpRequest


def team_name(request: HttpRequest) -> dict[str, str]:
    return {"TEAM_NAME": settings.TEAM_NAME}
