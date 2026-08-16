from collections.abc import Callable

import pytest
from django.contrib.auth.models import User
from django.test import Client


@pytest.fixture
def user(db: None) -> User:
    return User.objects.create_user(username="parent", password="secret-pass")


@pytest.fixture
def other_user(db: None) -> User:
    return User.objects.create_user(username="other", password="secret-pass")


@pytest.fixture
def client_for() -> Callable[[User], Client]:
    def make_client(account: User) -> Client:
        client = Client()
        client.force_login(account)
        return client

    return make_client
