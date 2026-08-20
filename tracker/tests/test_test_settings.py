from importlib import import_module

from django.db import connection


def test_test_settings_use_fast_local_test_defaults() -> None:
    settings = import_module("goalkeepr.test_settings")

    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"
    assert connection.vendor == "sqlite"
    assert "mode=memory" in connection.settings_dict["NAME"]
    assert settings.PASSWORD_HASHERS == [
        "django.contrib.auth.hashers.MD5PasswordHasher"
    ]
