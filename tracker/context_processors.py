from django.conf import settings
from django.http import HttpRequest


def primary_club_name(request: HttpRequest) -> dict[str, str]:
    return {"PRIMARY_CLUB_NAME": settings.PRIMARY_CLUB_NAME}
