import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

import tracker.models


@pytest.mark.django_db
def test_player_membership_hides_delete_control_and_direct_delete_conflicts(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
) -> None:
    player = tracker.models.Player.objects.create(name="Alex")
    tracker.models.TeamMembership.objects.create(player=player, team=primary_team)
    client.force_login(user)

    list_response = client.get(reverse("player-list"))
    delete_response = client.post(reverse("player-delete", args=[player.pk]))

    assert list_response.status_code == 200
    assert reverse("player-delete", args=[player.pk]) not in list_response.text
    assert "Recorded history" in list_response.text
    assert delete_response.status_code == 409
    assert "retained history" in delete_response.text
    assert tracker.models.Player.objects.filter(pk=player.pk).exists()


@pytest.mark.django_db
def test_team_membership_hides_delete_control_and_direct_delete_conflicts(
    client: Client,
    user: User,
    opponent_team: tracker.models.Team,
) -> None:
    player = tracker.models.Player.objects.create(name="Alex")
    tracker.models.TeamMembership.objects.create(player=player, team=opponent_team)
    client.force_login(user)

    list_response = client.get(reverse("team-list"))
    delete_response = client.post(reverse("team-delete", args=[opponent_team.pk]))

    assert list_response.status_code == 200
    assert reverse("team-delete", args=[opponent_team.pk]) not in list_response.text
    assert "Recorded history" in list_response.text
    assert delete_response.status_code == 409
    assert "retained history" in delete_response.text
    assert tracker.models.Team.objects.filter(pk=opponent_team.pk).exists()


@pytest.mark.django_db
def test_default_team_hides_delete_control_and_direct_delete_conflicts(
    client: Client,
    user: User,
    primary_team: tracker.models.Team,
) -> None:
    client.force_login(user)

    list_response = client.get(reverse("team-list"))
    delete_response = client.post(reverse("team-delete", args=[primary_team.pk]))

    assert list_response.status_code == 200
    assert reverse("team-delete", args=[primary_team.pk]) not in list_response.text
    assert "Application default" in list_response.text
    assert delete_response.status_code == 409
    assert "application defaults" in delete_response.text
    assert tracker.models.Team.objects.filter(pk=primary_team.pk).exists()
