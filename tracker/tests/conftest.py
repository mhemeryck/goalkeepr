import pytest
from django.contrib.auth.models import User


@pytest.fixture
def user(db: None) -> User:
    return User.objects.create_user(username="parent", password="secret-pass")


@pytest.fixture
def other_user(db: None) -> User:
    return User.objects.create_user(username="other", password="secret-pass")
