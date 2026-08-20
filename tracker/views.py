import typing

from asgiref.sync import sync_to_async
from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Case, Count, Q, QuerySet, Value, When
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

import tracker.forms
import tracker.models


class TeamResult(typing.TypedDict):
    team: tracker.models.Team
    wins: int
    draws: int
    losses: int
    match_count: int


class ScoredMatch(typing.Protocol):
    home_score_value: int
    away_score_value: int


MATCH_EDIT_FIELDS = {
    "opponent": "opponent_name",
    "venue": "is_home",
    "date": "match_date",
    "notes": "notes",
}
MATCH_EDIT_LABELS = {
    "opponent": "Opponent",
    "venue": "Venue",
    "date": "Date",
    "notes": "Notes",
}
SCOREBOARD_FIELDS = frozenset({"opponent", "venue", "date"})


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


async def _players_with_goal_counts() -> list[tracker.models.Player]:
    return [
        player
        async for player in tracker.models.Player.objects.annotate(
            goal_count=Count("score_events")
        ).order_by("name", "pk")
    ]


async def _teams_with_results() -> list[TeamResult]:
    results = {
        team.pk: TeamResult(
            team=team,
            wins=0,
            draws=0,
            losses=0,
            match_count=0,
        )
        async for team in tracker.models.Team.objects.all()
    }
    matches = [
        match async for match in _scored_matches(tracker.models.Match.objects.all())
    ]
    today = timezone.localdate()
    for match in matches:
        result = results[match.opponent_id]
        result["match_count"] += 1
        if match.match_date > today:
            continue
        scored_match = typing.cast(ScoredMatch, match)
        home_score = scored_match.home_score_value
        away_score = scored_match.away_score_value
        household_score = home_score if match.is_home else away_score
        opponent_score = away_score if match.is_home else home_score
        if household_score > opponent_score:
            result["wins"] += 1
        elif household_score < opponent_score:
            result["losses"] += 1
        else:
            result["draws"] += 1
    return list(results.values())


async def _team_result(pk: int) -> TeamResult | None:
    return next(
        (result for result in await _teams_with_results() if result["team"].pk == pk),
        None,
    )


async def _score_context(
    match: tracker.models.Match,
    *,
    can_modify: bool,
) -> dict[str, typing.Any]:
    team_name = str(settings.TEAM_NAME)
    events = [
        event async for event in match.score_events.select_related("scorer").all()
    ]
    is_future_fixture = _is_future_fixture(match)
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
        "player_names": (
            await _player_names() if can_modify and not is_future_fixture else []
        ),
        "events": events,
        "can_modify": can_modify,
        "is_future_fixture": is_future_fixture,
    }


async def _match_detail_context(
    match: tracker.models.Match,
    *,
    can_modify: bool,
    editing_field: str | None = None,
    edit_form: tracker.forms.MatchForm | None = None,
) -> dict[str, typing.Any]:
    context = await _score_context(match, can_modify=can_modify)
    if editing_field is not None and edit_form is not None:
        form_field_name = MATCH_EDIT_FIELDS[editing_field]
        context["editing_field"] = editing_field
        context["form"] = edit_form
        context["edit_field"] = edit_form[form_field_name]
        context["field_label"] = MATCH_EDIT_LABELS[editing_field]
        if editing_field == "opponent":
            context["opponent_names"] = await _team_names()
    return context


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
        match = form.save(commit=False)
        if "opponent_name" in form.cleaned_data:
            name = str(form.cleaned_data["opponent_name"])
            opponent = tracker.models.Team.objects.filter(name__iexact=name).first()
            if opponent is None:
                try:
                    with transaction.atomic():
                        opponent = tracker.models.Team.objects.create(name=name)
                except IntegrityError:
                    opponent = tracker.models.Team.objects.get(name__iexact=name)
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
    return render(
        request,
        "tracker/player_list.html",
        {"players": await _players_with_goal_counts()},
    )


@login_required
async def player_edit(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        player = await tracker.models.Player.objects.annotate(
            goal_count=Count("score_events")
        ).aget(pk=pk)
    except tracker.models.Player.DoesNotExist:
        return await _not_found_response(request)
    request.user = await request.auser()
    form = tracker.forms.PlayerForm(request.POST or None, instance=player)
    if request.method == "POST" and await _form_is_valid(form):
        await sync_to_async(form.save)()
        if request.headers.get("HX-Request") == "true":
            player = await tracker.models.Player.objects.annotate(
                goal_count=Count("score_events")
            ).aget(pk=pk)
            return render(
                request,
                "tracker/partials/player_row.html",
                {"player": player},
            )
        return redirect("player-list")
    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "tracker/partials/player_edit_row.html",
            {"player": player, "form": form},
        )
    return render(
        request,
        "tracker/player_list.html",
        {
            "players": await _players_with_goal_counts(),
            "edit_form": form,
            "editing_player_id": player.pk,
        },
        status=400 if form.is_bound else 200,
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
async def team_list(request: HttpRequest) -> HttpResponse:
    request.user = await request.auser()
    return render(
        request,
        "tracker/team_list.html",
        {"teams": await _teams_with_results()},
    )


@login_required
async def team_edit(request: HttpRequest, pk: int) -> HttpResponse:
    result = await _team_result(pk)
    if result is None:
        return await _not_found_response(request)
    request.user = await request.auser()
    team = result["team"]
    form = tracker.forms.TeamForm(request.POST or None, instance=team)
    if request.method == "POST" and await _form_is_valid(form):
        await sync_to_async(form.save)()
        if request.headers.get("HX-Request") == "true":
            result = await _team_result(pk)
            return render(
                request,
                "tracker/partials/team_row.html",
                {"result": result},
            )
        return redirect("team-list")
    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "tracker/partials/team_edit_row.html",
            {"result": result, "form": form},
        )
    return render(
        request,
        "tracker/team_list.html",
        {
            "teams": await _teams_with_results(),
            "edit_form": form,
            "editing_team_id": team.pk,
        },
        status=400 if form.is_bound else 200,
    )


@require_POST
@login_required
async def team_delete(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        team = await tracker.models.Team.objects.aget(pk=pk)
    except tracker.models.Team.DoesNotExist:
        return await _not_found_response(request)
    request.user = await request.auser()
    if not await team.matches.aexists():
        await team.adelete()
    return redirect("team-list")


@login_required
async def match_create(request: HttpRequest) -> HttpResponse:
    request.user = await request.auser()
    form = tracker.forms.MatchForm(request.POST or None)
    if request.method == "POST" and await _form_is_valid(form):
        match = await sync_to_async(_save_match_form)(form)
        return redirect("match-detail", pk=match.pk)
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
    user = await request.auser()
    request.user = user
    editing_field = request.GET.get("edit")
    edit_form = None
    if user.is_authenticated and editing_field in MATCH_EDIT_FIELDS:
        form_field_name = MATCH_EDIT_FIELDS[editing_field]
        edit_form = tracker.forms.MatchForm(
            instance=match,
            editable_field=form_field_name,
        )
        edit_form.fields[form_field_name].widget.attrs["autofocus"] = True
    else:
        editing_field = None
    context = await _match_detail_context(
        match,
        can_modify=user.is_authenticated,
        editing_field=editing_field,
        edit_form=edit_form,
    )
    return render(request, "tracker/match_detail.html", context)


@login_required
async def match_edit(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        match = await tracker.models.Match.objects.select_related("opponent").aget(
            pk=pk
        )
    except tracker.models.Match.DoesNotExist:
        return await _not_found_response(request)
    return redirect("match-detail", pk=match.pk)


@login_required
async def match_field_edit(
    request: HttpRequest,
    pk: int,
    field_name: str,
) -> HttpResponse:
    if field_name not in MATCH_EDIT_FIELDS:
        return await _not_found_response(request)
    try:
        match = await tracker.models.Match.objects.select_related("opponent").aget(
            pk=pk
        )
    except tracker.models.Match.DoesNotExist:
        return await _not_found_response(request)
    request.user = await request.auser()
    original_is_home = match.is_home
    form_field_name = MATCH_EDIT_FIELDS[field_name]
    form = tracker.forms.MatchForm(
        request.POST or None,
        instance=match,
        editable_field=form_field_name,
    )
    form.fields[form_field_name].widget.attrs["autofocus"] = True
    if request.method == "POST" and await _form_is_valid(form):
        match = await sync_to_async(_save_match_form)(form, original_is_home)
        if request.headers.get("HX-Request") == "true":
            context: dict[str, typing.Any] = {
                "match": match,
                "can_modify": True,
                "field_name": field_name,
                "field_label": MATCH_EDIT_LABELS[field_name],
                "refresh_match": field_name in SCOREBOARD_FIELDS,
            }
            if context["refresh_match"]:
                context.update(await _score_context(match, can_modify=True))
            return render(
                request,
                "tracker/partials/match_detail_row_saved.html",
                context,
            )
        return redirect("match-detail", pk=match.pk)
    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "tracker/partials/match_detail_edit_row.html",
            {
                "match": match,
                "form": form,
                "field": form[form_field_name],
                "field_name": field_name,
                "field_label": MATCH_EDIT_LABELS[field_name],
                "opponent_names": (
                    await _team_names() if field_name == "opponent" else []
                ),
            },
        )
    if not form.is_bound:
        detail_url = reverse("match-detail", args=[match.pk])
        return redirect(f"{detail_url}?edit={field_name}")
    match = await tracker.models.Match.objects.select_related("opponent").aget(pk=pk)
    return render(
        request,
        "tracker/match_detail.html",
        await _match_detail_context(
            match,
            can_modify=True,
            editing_field=field_name,
            edit_form=form,
        ),
        status=400,
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
    return redirect("match-detail", pk=match.pk)


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
    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "tracker/partials/scoreboard.html",
            await _score_context(match, can_modify=True),
        )
    return redirect("match-detail", pk=match.pk)


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
    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "tracker/partials/scoreboard.html",
            await _score_context(match, can_modify=True),
        )
    return redirect("match-detail", pk=match.pk)
