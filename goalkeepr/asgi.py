import os

from django.conf import settings
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "goalkeepr.settings")

django_application = get_asgi_application()
application = (
    ASGIStaticFilesHandler(django_application) if settings.DEBUG else django_application
)
