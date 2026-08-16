import typing

from asgiref.sync import sync_to_async
from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Q, QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

import tracker.forms
import tracker.models


async def _form_is_valid(form: forms.BaseForm) -> bool:
    return await sync_to_async(form.is_valid)()


async def _authenticated_user(request: HttpRequest) -> User:
    user = await request.auser()
    if not isinstance(user, User):
        raise Http404
    request.user = user
    return user


async def _owned_match(user: User, pk: int) -> tracker.models.Match:
    try:
        return await tracker.models.Match.objects.aget(pk=pk, owner=user)
    except tracker.models.Match.DoesNotExist as error:
        raise Http404 from error


async def _match(pk: int) -> tracker.models.Match:
    try:
        return await tracker.models.Match.objects.aget(pk=pk)
    except tracker.models.Match.DoesNotExist as error:
        raise Http404 from error


def _scored_matches(
    queryset: QuerySet[tracker.models.Match],
) -> QuerySet[tracker.models.Match]:
    return queryset.annotate(
        home_score_value=Count(
            "score_events",
            filter=Q(score_events__side=tracker.models.ScoreEvent.Side.HOME),
        ),
        away_score_value=Count(
            "score_events",
            filter=Q(score_events__side=tracker.models.ScoreEvent.Side.AWAY),
        ),
    )


async def _score_context(match: tracker.models.Match) -> dict[str, typing.Any]:
    team_name = str(settings.TEAM_NAME)
    return {
        "match": match,
        "home_name": team_name if match.is_home else match.opponent_name,
        "away_name": match.opponent_name if match.is_home else team_name,
        "home_score": await match.score_events.filter(
            side=tracker.models.ScoreEvent.Side.HOME
        ).acount(),
        "away_score": await match.score_events.filter(
            side=tracker.models.ScoreEvent.Side.AWAY
        ).acount(),
    }


async def match_list(request: HttpRequest) -> HttpResponse:
    request.user = await request.auser()
    matches = [
        match
        async for match in _scored_matches(tracker.models.Match.objects.all()).order_by(
            "-match_date", "-pk"
        )
    ]
    return render(request, "tracker/match_list.html", {"matches": matches})


@login_required
async def match_create(request: HttpRequest) -> HttpResponse:
    user = await _authenticated_user(request)
    form = tracker.forms.MatchForm(request.POST or None)
    if request.method == "POST" and await _form_is_valid(form):
        match = form.save(commit=False)
        match.owner = user
        await match.asave()
        return redirect("match-score", pk=match.pk)
    return render(
        request,
        "tracker/form.html",
        {"form": form, "title": "Add match"},
    )


async def match_detail(request: HttpRequest, pk: int) -> HttpResponse:
    match = await _match(pk)
    events = [event async for event in match.score_events.all()]
    user = await request.auser()
    request.user = user
    context = await _score_context(match)
    context["events"] = events
    context["can_modify"] = user.is_authenticated and user.pk == match.owner_id
    return render(request, "tracker/match_detail.html", context)


@login_required
async def match_edit(request: HttpRequest, pk: int) -> HttpResponse:
    user = await _authenticated_user(request)
    match = await _owned_match(user, pk)
    form = tracker.forms.MatchForm(request.POST or None, instance=match)
    if request.method == "POST" and await _form_is_valid(form):
        await sync_to_async(form.save)()
        return redirect("match-detail", pk=match.pk)
    return render(
        request,
        "tracker/form.html",
        {"form": form, "title": "Edit match"},
    )


@login_required
async def match_delete(request: HttpRequest, pk: int) -> HttpResponse:
    user = await _authenticated_user(request)
    match = await _owned_match(user, pk)
    if request.method == "POST":
        await match.adelete()
        return redirect("match-list")
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
    return side in tracker.models.ScoreEvent.Side.values


@require_POST
@login_required
async def score_goal(request: HttpRequest, pk: int, side: str) -> HttpResponse:
    user = await _authenticated_user(request)
    match = await _owned_match(user, pk)
    if not _valid_side(side):
        raise Http404
    await tracker.models.ScoreEvent.objects.acreate(match=match, side=side)
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
    event = await tracker.models.ScoreEvent.objects.filter(
        match=match, side=side
    ).afirst()
    if event is not None:
        await event.adelete()
    return render(
        request, "tracker/partials/scoreboard.html", await _score_context(match)
    )
