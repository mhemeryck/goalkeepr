from typing import Any

from asgiref.sync import sync_to_async
from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Q, QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from tracker.forms import MatchForm, SeasonForm, TeamForm
from tracker.models import Match, ScoreEvent, Season, Team


async def _form_is_valid(form: forms.BaseForm) -> bool:
    return await sync_to_async(form.is_valid)()


async def _authenticated_user(request: HttpRequest) -> User:
    user = await request.auser()
    if not isinstance(user, User):
        raise Http404
    request.user = user
    return user


async def _owned_team(user: User, pk: int) -> Team:
    try:
        return await Team.objects.aget(pk=pk, owner=user)
    except Team.DoesNotExist as error:
        raise Http404 from error


async def _owned_season(user: User, pk: int) -> Season:
    try:
        return await Season.objects.select_related("team").aget(pk=pk, team__owner=user)
    except Season.DoesNotExist as error:
        raise Http404 from error


async def _owned_match(user: User, pk: int) -> Match:
    try:
        return await Match.objects.select_related("season__team").aget(
            pk=pk,
            season__team__owner=user,
        )
    except Match.DoesNotExist as error:
        raise Http404 from error


def _scored_matches(queryset: QuerySet[Match]) -> QuerySet[Match]:
    return queryset.annotate(
        home_score_value=Count(
            "score_events",
            filter=Q(score_events__side=ScoreEvent.Side.HOME),
        ),
        away_score_value=Count(
            "score_events",
            filter=Q(score_events__side=ScoreEvent.Side.AWAY),
        ),
    )


async def _score_context(match: Match) -> dict[str, Any]:
    return {
        "match": match,
        "home_score": await match.score_events.filter(
            side=ScoreEvent.Side.HOME
        ).acount(),
        "away_score": await match.score_events.filter(
            side=ScoreEvent.Side.AWAY
        ).acount(),
    }


@login_required
async def match_list(request: HttpRequest) -> HttpResponse:
    user = await _authenticated_user(request)
    matches = [
        match
        async for match in _scored_matches(
            Match.objects.filter(season__team__owner=user).select_related(
                "season__team"
            )
        )
    ]
    return render(request, "tracker/match_list.html", {"matches": matches})


@login_required
async def team_list(request: HttpRequest) -> HttpResponse:
    user = await _authenticated_user(request)
    teams = [team async for team in Team.objects.filter(owner=user)]
    return render(request, "tracker/team_list.html", {"teams": teams})


@login_required
async def team_create(request: HttpRequest) -> HttpResponse:
    user = await _authenticated_user(request)
    form = TeamForm(request.POST or None)
    if request.method == "POST" and await _form_is_valid(form):
        team = form.save(commit=False)
        team.owner = user
        await team.asave()
        return redirect("team-detail", pk=team.pk)
    return render(request, "tracker/form.html", {"form": form, "title": "Add team"})


@login_required
async def team_edit(request: HttpRequest, pk: int) -> HttpResponse:
    user = await _authenticated_user(request)
    team = await _owned_team(user, pk)
    form = TeamForm(request.POST or None, instance=team)
    if request.method == "POST" and await _form_is_valid(form):
        await sync_to_async(form.save)()
        return redirect("team-detail", pk=team.pk)
    return render(request, "tracker/form.html", {"form": form, "title": "Edit team"})


@login_required
async def team_detail(request: HttpRequest, pk: int) -> HttpResponse:
    user = await _authenticated_user(request)
    team = await _owned_team(user, pk)
    seasons = [season async for season in team.seasons.all()]
    return render(
        request,
        "tracker/team_detail.html",
        {"team": team, "seasons": seasons},
    )


@login_required
async def team_delete(request: HttpRequest, pk: int) -> HttpResponse:
    user = await _authenticated_user(request)
    team = await _owned_team(user, pk)
    if request.method == "POST":
        await team.adelete()
        return redirect("team-list")
    return render(
        request, "tracker/confirm_delete.html", {"object": team, "kind": "team"}
    )


@login_required
async def season_create(request: HttpRequest, team_pk: int) -> HttpResponse:
    user = await _authenticated_user(request)
    team = await _owned_team(user, team_pk)
    form = SeasonForm(request.POST or None)
    if request.method == "POST" and await _form_is_valid(form):
        season = form.save(commit=False)
        season.team = team
        await season.asave()
        return redirect("season-detail", pk=season.pk)
    return render(
        request,
        "tracker/form.html",
        {"form": form, "title": f"Add season for {team.name}"},
    )


@login_required
async def season_detail(request: HttpRequest, pk: int) -> HttpResponse:
    user = await _authenticated_user(request)
    season = await _owned_season(user, pk)
    matches = [
        match
        async for match in _scored_matches(
            season.matches.select_related("season__team").all()
        )
    ]
    return render(
        request,
        "tracker/season_detail.html",
        {"season": season, "matches": matches},
    )


@login_required
async def season_edit(request: HttpRequest, pk: int) -> HttpResponse:
    user = await _authenticated_user(request)
    season = await _owned_season(user, pk)
    form = SeasonForm(request.POST or None, instance=season)
    if request.method == "POST" and await _form_is_valid(form):
        await sync_to_async(form.save)()
        return redirect("season-detail", pk=season.pk)
    return render(request, "tracker/form.html", {"form": form, "title": "Edit season"})


@login_required
async def season_delete(request: HttpRequest, pk: int) -> HttpResponse:
    user = await _authenticated_user(request)
    season = await _owned_season(user, pk)
    team_pk = season.team_id
    if request.method == "POST":
        await season.adelete()
        return redirect("team-detail", pk=team_pk)
    return render(
        request,
        "tracker/confirm_delete.html",
        {"object": season, "kind": "season"},
    )


@login_required
async def match_create(request: HttpRequest, season_pk: int) -> HttpResponse:
    user = await _authenticated_user(request)
    season = await _owned_season(user, season_pk)
    form = MatchForm(request.POST or None)
    if request.method == "POST" and await _form_is_valid(form):
        match = form.save(commit=False)
        match.season = season
        await match.asave()
        return redirect("match-score", pk=match.pk)
    return render(
        request,
        "tracker/form.html",
        {"form": form, "title": f"Add match to {season.name}"},
    )


@login_required
async def match_detail(request: HttpRequest, pk: int) -> HttpResponse:
    user = await _authenticated_user(request)
    match = await _owned_match(user, pk)
    events = [event async for event in match.score_events.all()]
    context = await _score_context(match)
    context["events"] = events
    return render(request, "tracker/match_detail.html", context)


@login_required
async def match_edit(request: HttpRequest, pk: int) -> HttpResponse:
    user = await _authenticated_user(request)
    match = await _owned_match(user, pk)
    form = MatchForm(request.POST or None, instance=match)
    if request.method == "POST" and await _form_is_valid(form):
        await sync_to_async(form.save)()
        return redirect("match-detail", pk=match.pk)
    return render(request, "tracker/form.html", {"form": form, "title": "Edit match"})


@login_required
async def match_delete(request: HttpRequest, pk: int) -> HttpResponse:
    user = await _authenticated_user(request)
    match = await _owned_match(user, pk)
    season_pk = match.season_id
    if request.method == "POST":
        await match.adelete()
        return redirect("season-detail", pk=season_pk)
    return render(
        request,
        "tracker/confirm_delete.html",
        {"object": match, "kind": "match"},
    )


@login_required
async def match_score(request: HttpRequest, pk: int) -> HttpResponse:
    user = await _authenticated_user(request)
    match = await _owned_match(user, pk)
    return render(request, "tracker/match_score.html", await _score_context(match))


def _valid_side(side: str) -> bool:
    return side in ScoreEvent.Side.values


@require_POST
@login_required
async def score_goal(request: HttpRequest, pk: int, side: str) -> HttpResponse:
    user = await _authenticated_user(request)
    match = await _owned_match(user, pk)
    if not _valid_side(side):
        raise Http404
    await ScoreEvent.objects.acreate(match=match, side=side)
    return render(
        request, "tracker/partials/scoreboard.html", await _score_context(match)
    )


@require_POST
@login_required
async def score_undo(request: HttpRequest, pk: int, side: str) -> HttpResponse:
    user = await _authenticated_user(request)
    match = await _owned_match(user, pk)
    if not _valid_side(side):
        raise Http404
    event = await match.score_events.filter(side=side).afirst()
    if event is not None:
        await event.adelete()
    return render(
        request, "tracker/partials/scoreboard.html", await _score_context(match)
    )
