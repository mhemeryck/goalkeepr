import typing

from asgiref.sync import sync_to_async
from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Case, Count, Q, QuerySet, Value, When
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

import tracker.forms
import tracker.models


async def _form_is_valid(form: forms.BaseForm) -> bool:
    return await sync_to_async(form.is_valid)()


async def _not_found_response(request: HttpRequest) -> HttpResponse:
    request.user = await request.auser()
    return render(request, "404.html", status=404)


def _is_future_fixture(match: tracker.models.Match) -> bool:
    return match.match_date > timezone.localdate()


def _scored_matches(
    queryset: QuerySet[tracker.models.Match],
) -> QuerySet[tracker.models.Match]:
    return queryset.select_related("opponent").annotate(
        home_score_value=Count(
            "score_events",
            filter=Q(score_events__side=tracker.models.ScoreEvent.Side.HOME),
        ),
        away_score_value=Count(
            "score_events",
            filter=Q(score_events__side=tracker.models.ScoreEvent.Side.AWAY),
        ),
    )


async def _match_list_context() -> dict[str, typing.Any]:
    matches = [
        match
        async for match in _scored_matches(tracker.models.Match.objects.all()).order_by(
            "-match_date", "-pk"
        )
    ]
    return {"matches": matches, "today": timezone.localdate()}


async def _player_names() -> list[str]:
    return [
        name
        async for name in tracker.models.Player.objects.order_by("name").values_list(
            "name", flat=True
        )
    ]


async def _team_names() -> list[str]:
    return [
        name
        async for name in tracker.models.Team.objects.order_by("name").values_list(
            "name", flat=True
        )
    ]


async def _score_context(match: tracker.models.Match) -> dict[str, typing.Any]:
    team_name = str(settings.TEAM_NAME)
    recent_events = [
        event async for event in match.score_events.select_related("scorer").all()[:5]
    ]
    return {
        "match": match,
        "home_name": team_name if match.is_home else match.opponent.name,
        "away_name": match.opponent.name if match.is_home else team_name,
        "home_score": await match.score_events.filter(
            side=tracker.models.ScoreEvent.Side.HOME
        ).acount(),
        "away_score": await match.score_events.filter(
            side=tracker.models.ScoreEvent.Side.AWAY
        ).acount(),
        "household_side": (
            tracker.models.ScoreEvent.Side.HOME
            if match.is_home
            else tracker.models.ScoreEvent.Side.AWAY
        ),
        "player_names": await _player_names(),
        "recent_events": recent_events,
    }


async def _form_context(
    form: tracker.forms.MatchForm,
    title: str,
) -> dict[str, typing.Any]:
    return {
        "form": form,
        "title": title,
        "opponent_names": await _team_names(),
    }


def _save_match_form(
    form: tracker.forms.MatchForm,
    original_is_home: bool | None = None,
) -> tracker.models.Match:
    with transaction.atomic():
        name = str(form.cleaned_data["opponent_name"])
        opponent = tracker.models.Team.objects.filter(name__iexact=name).first()
        if opponent is None:
            try:
                with transaction.atomic():
                    opponent = tracker.models.Team.objects.create(name=name)
            except IntegrityError:
                opponent = tracker.models.Team.objects.get(name__iexact=name)
        match = form.save(commit=False)
        match.opponent = opponent
        match.save()
        if original_is_home is not None and original_is_home != match.is_home:
            match.score_events.update(
                side=Case(
                    When(
                        side=tracker.models.ScoreEvent.Side.HOME,
                        then=Value(tracker.models.ScoreEvent.Side.AWAY),
                    ),
                    default=Value(tracker.models.ScoreEvent.Side.HOME),
                )
            )
        return match


def _get_or_create_player(name: str) -> tracker.models.Player:
    with transaction.atomic():
        player = tracker.models.Player.objects.filter(name__iexact=name).first()
        if player is not None:
            return player
        try:
            with transaction.atomic():
                return tracker.models.Player.objects.create(name=name)
        except IntegrityError:
            return tracker.models.Player.objects.get(name__iexact=name)


async def match_list(request: HttpRequest) -> HttpResponse:
    request.user = await request.auser()
    return render(request, "tracker/match_list.html", await _match_list_context())


async def match_list_fragment(request: HttpRequest) -> HttpResponse:
    request.user = await request.auser()
    return render(
        request,
        "tracker/partials/match_list.html",
        await _match_list_context(),
    )


@login_required
async def player_list(request: HttpRequest) -> HttpResponse:
    request.user = await request.auser()
    players = [
        player
        async for player in tracker.models.Player.objects.annotate(
            goal_count=Count("score_events")
        ).order_by("name", "pk")
    ]
    return render(request, "tracker/player_list.html", {"players": players})


@require_POST
@login_required
async def player_edit(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        player = await tracker.models.Player.objects.aget(pk=pk)
    except tracker.models.Player.DoesNotExist:
        return await _not_found_response(request)
    request.user = await request.auser()
    form = tracker.forms.PlayerForm(request.POST or None, instance=player)
    if await _form_is_valid(form):
        await sync_to_async(form.save)()
        return redirect("player-list")
    players = [
        item
        async for item in tracker.models.Player.objects.annotate(
            goal_count=Count("score_events")
        ).order_by("name", "pk")
    ]
    return render(
        request,
        "tracker/player_list.html",
        {
            "players": players,
            "edit_form": form,
            "editing_player_id": player.pk,
        },
        status=400,
    )


@require_POST
@login_required
async def player_delete(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        player = await tracker.models.Player.objects.aget(pk=pk)
    except tracker.models.Player.DoesNotExist:
        return await _not_found_response(request)
    request.user = await request.auser()
    await player.adelete()
    return redirect("player-list")


@login_required
async def match_create(request: HttpRequest) -> HttpResponse:
    request.user = await request.auser()
    form = tracker.forms.MatchForm(request.POST or None)
    if request.method == "POST" and await _form_is_valid(form):
        match = await sync_to_async(_save_match_form)(form)
        if _is_future_fixture(match):
            return redirect("match-detail", pk=match.pk)
        return redirect("match-score", pk=match.pk)
    return render(
        request,
        "tracker/form.html",
        await _form_context(form, "Add match"),
    )


async def match_detail(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        match = await tracker.models.Match.objects.select_related("opponent").aget(
            pk=pk
        )
    except tracker.models.Match.DoesNotExist:
        return await _not_found_response(request)
    events = [
        event async for event in match.score_events.select_related("scorer").all()
    ]
    user = await request.auser()
    request.user = user
    context = await _score_context(match)
    context["events"] = events
    context["can_modify"] = user.is_authenticated
    context["is_future_fixture"] = _is_future_fixture(match)
    return render(request, "tracker/match_detail.html", context)


@login_required
async def match_edit(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        match = await tracker.models.Match.objects.select_related("opponent").aget(
            pk=pk
        )
    except tracker.models.Match.DoesNotExist:
        return await _not_found_response(request)
    request.user = await request.auser()
    original_is_home = match.is_home
    form = tracker.forms.MatchForm(request.POST or None, instance=match)
    if request.method == "POST" and await _form_is_valid(form):
        await sync_to_async(_save_match_form)(form, original_is_home)
        return redirect("match-detail", pk=match.pk)
    return render(
        request,
        "tracker/form.html",
        await _form_context(form, "Edit match"),
    )


@login_required
async def match_delete(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        match = await tracker.models.Match.objects.select_related("opponent").aget(
            pk=pk
        )
    except tracker.models.Match.DoesNotExist:
        return await _not_found_response(request)
    if request.method == "POST":
        await match.adelete()
        return redirect("match-list")
    request.user = await request.auser()
    return render(
        request,
        "tracker/confirm_delete.html",
        {"object": match, "kind": "match"},
    )


@login_required
async def match_score(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        match = await tracker.models.Match.objects.select_related("opponent").aget(
            pk=pk
        )
    except tracker.models.Match.DoesNotExist:
        return await _not_found_response(request)
    if _is_future_fixture(match):
        return redirect("match-detail", pk=match.pk)
    request.user = await request.auser()
    return render(request, "tracker/match_score.html", await _score_context(match))


@require_POST
@login_required
async def score_goal(
    request: HttpRequest,
    pk: int,
    side: tracker.models.ScoreEvent.Side,
) -> HttpResponse:
    try:
        match = await tracker.models.Match.objects.select_related("opponent").aget(
            pk=pk
        )
    except tracker.models.Match.DoesNotExist:
        return await _not_found_response(request)
    if _is_future_fixture(match):
        return HttpResponseForbidden("Future fixtures cannot be scored.")

    scorer = None
    household_side = (
        tracker.models.ScoreEvent.Side.HOME
        if match.is_home
        else tracker.models.ScoreEvent.Side.AWAY
    )
    if side == household_side:
        form = tracker.forms.GoalForm(request.POST)
        if not await _form_is_valid(form):
            return HttpResponse("Invalid scorer.", status=400)
        scorer_name = str(form.cleaned_data["scorer_name"])
        if scorer_name:
            scorer = await sync_to_async(_get_or_create_player)(scorer_name)

    await tracker.models.ScoreEvent.objects.acreate(
        match=match,
        side=side,
        scorer=scorer,
    )
    return render(
        request, "tracker/partials/scoreboard.html", await _score_context(match)
    )


@require_POST
@login_required
async def score_undo(
    request: HttpRequest,
    pk: int,
    side: tracker.models.ScoreEvent.Side,
) -> HttpResponse:
    try:
        match = await tracker.models.Match.objects.select_related("opponent").aget(
            pk=pk
        )
    except tracker.models.Match.DoesNotExist:
        return await _not_found_response(request)
    if _is_future_fixture(match):
        return HttpResponseForbidden("Future fixtures cannot be scored.")
    event = await tracker.models.ScoreEvent.objects.filter(
        match=match, side=side
    ).afirst()
    if event is not None:
        await event.adelete()
    return render(
        request, "tracker/partials/scoreboard.html", await _score_context(match)
    )
