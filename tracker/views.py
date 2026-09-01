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
    "home-team": "home_team",
    "away-team": "away_team",
    "date": "match_date",
    "status": "status",
    "notes": "notes",
}
MATCH_EDIT_LABELS = {
    "home-team": "Home team",
    "away-team": "Away team",
    "date": "Date",
    "status": "Status",
    "notes": "Notes",
}
SCOREBOARD_FIELDS = frozenset({"home-team", "away-team", "date", "status"})


async def _form_is_valid(form: forms.BaseForm) -> bool:
    return await sync_to_async(form.is_valid)()


async def _not_found_response(request: HttpRequest) -> HttpResponse:
    request.user = await request.auser()
    return render(request, "404.html", status=404)


def _scored_matches(
    queryset: QuerySet[tracker.models.Match],
) -> QuerySet[tracker.models.Match]:
    return queryset.select_related(
        "home_team__club",
        "home_team__season",
        "away_team__club",
        "away_team__season",
    ).annotate(
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
        match async for match in _scored_matches(tracker.models.Match.objects.all())
    ]
    return {"matches": matches, "primary_club_name": settings.PRIMARY_CLUB_NAME}


async def _player_names(team: tracker.models.Team) -> list[str]:
    return [
        name
        async for name in tracker.models.Player.objects.filter(teams=team)
        .order_by("name")
        .values_list("name", flat=True)
    ]


async def _team_choices() -> list[tuple[int, str]]:
    today = timezone.localdate()
    return [
        (team.pk, f"{team} ({team.season})")
        async for team in tracker.models.Team.objects.select_related("club", "season")
        .alias(
            current_season_order=Case(
                When(
                    season__start_date__lte=today,
                    season__end_date__gte=today,
                    then=Value(0),
                ),
                default=Value(1),
            )
        )
        .order_by(
            "current_season_order",
            "-season__start_date",
            "club__name",
            "age_group",
            "designation",
        )
    ]


async def _set_team_choices(form: tracker.forms.MatchForm) -> None:
    choices = [("", "---------"), *(await _team_choices())]
    for field_name in ("home_team", "away_team"):
        if field_name in form.fields:
            typing.cast(forms.ChoiceField, form.fields[field_name]).choices = choices


async def _age_groups() -> list[str]:
    return [
        age_group
        async for age_group in tracker.models.Team.objects.order_by("age_group")
        .values_list("age_group", flat=True)
        .distinct()
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
        team.pk: TeamResult(team=team, wins=0, draws=0, losses=0, match_count=0)
        async for team in tracker.models.Team.objects.select_related("club", "season")
    }
    matches = [
        match async for match in _scored_matches(tracker.models.Match.objects.all())
    ]
    for match in matches:
        home_result = results[match.home_team_id]
        away_result = results[match.away_team_id]
        home_result["match_count"] += 1
        away_result["match_count"] += 1
        if match.status != tracker.models.Match.Status.FINISHED:
            continue
        scored_match = typing.cast(ScoredMatch, match)
        if scored_match.home_score_value > scored_match.away_score_value:
            home_result["wins"] += 1
            away_result["losses"] += 1
        elif scored_match.home_score_value < scored_match.away_score_value:
            home_result["losses"] += 1
            away_result["wins"] += 1
        else:
            home_result["draws"] += 1
            away_result["draws"] += 1
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
    events = [event async for event in match.score_events.select_related("scorer")]
    show_score = match.status in {
        tracker.models.Match.Status.LIVE,
        tracker.models.Match.Status.FINISHED,
    }
    can_score = can_modify and show_score
    return {
        "match": match,
        "home_name": str(match.home_team),
        "away_name": str(match.away_team),
        "home_score": await match.score_events.filter(
            side=tracker.models.ScoreEvent.Side.HOME
        ).acount(),
        "away_score": await match.score_events.filter(
            side=tracker.models.ScoreEvent.Side.AWAY
        ).acount(),
        "home_player_names": await _player_names(match.home_team) if can_score else [],
        "away_player_names": await _player_names(match.away_team) if can_score else [],
        "events": events if show_score else [],
        "can_modify": can_modify,
        "can_score": can_score,
        "show_score": show_score,
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
        context.update(
            editing_field=editing_field,
            form=edit_form,
            edit_field=edit_form[form_field_name],
            field_label=MATCH_EDIT_LABELS[editing_field],
        )
    return context


def _save_match_form(form: tracker.forms.MatchForm) -> tracker.models.Match:
    match = form.save(commit=False)
    match.full_clean()
    match.save()
    return match


def _get_or_create_player(
    name: str, team: tracker.models.Team
) -> tracker.models.Player:
    with transaction.atomic():
        player = tracker.models.Player.objects.filter(name__iexact=name).first()
        if player is None:
            try:
                with transaction.atomic():
                    player = tracker.models.Player.objects.create(name=name)
            except IntegrityError:
                player = tracker.models.Player.objects.get(name__iexact=name)
        tracker.models.TeamMembership.objects.get_or_create(player=player, team=team)
        return player


async def match_list(request: HttpRequest) -> HttpResponse:
    request.user = await request.auser()
    return render(request, "tracker/match_list.html", await _match_list_context())


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
                request, "tracker/partials/player_row.html", {"player": player}
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
        request, "tracker/team_list.html", {"teams": await _teams_with_results()}
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
            return render(
                request,
                "tracker/partials/team_row.html",
                {"result": await _team_result(pk)},
            )
        return redirect("team-list")
    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "tracker/partials/team_edit_row.html",
            {"result": result, "form": form, "age_groups": await _age_groups()},
        )
    return render(
        request,
        "tracker/team_list.html",
        {
            "teams": await _teams_with_results(),
            "edit_form": form,
            "editing_team_id": team.pk,
            "age_groups": await _age_groups(),
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
    used = await tracker.models.Match.objects.filter(
        Q(home_team=team) | Q(away_team=team)
    ).aexists()
    if not used:
        await team.adelete()
    return redirect("team-list")


@login_required
async def match_create(request: HttpRequest) -> HttpResponse:
    request.user = await request.auser()
    form = tracker.forms.MatchForm(request.POST or None)
    await _set_team_choices(form)
    if request.method == "POST" and await _form_is_valid(form):
        match = await sync_to_async(_save_match_form)(form)
        return redirect("match-detail", pk=match.pk)
    return render(request, "tracker/form.html", {"form": form, "title": "Add match"})


async def _get_match(pk: int) -> tracker.models.Match:
    return await tracker.models.Match.objects.select_related(
        "home_team__club", "home_team__season", "away_team__club", "away_team__season"
    ).aget(pk=pk)


async def match_detail(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        match = await _get_match(pk)
    except tracker.models.Match.DoesNotExist:
        return await _not_found_response(request)
    user = await request.auser()
    request.user = user
    editing_field = request.GET.get("edit")
    edit_form = None
    if user.is_authenticated and editing_field in MATCH_EDIT_FIELDS:
        form_field_name = MATCH_EDIT_FIELDS[editing_field]
        edit_form = tracker.forms.MatchForm(
            instance=match, editable_field=form_field_name
        )
        await _set_team_choices(edit_form)
        edit_form.fields[form_field_name].widget.attrs["autofocus"] = True
    else:
        editing_field = None
    return render(
        request,
        "tracker/match_detail.html",
        await _match_detail_context(
            match,
            can_modify=user.is_authenticated,
            editing_field=editing_field,
            edit_form=edit_form,
        ),
    )


async def match_detail_fragment(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        match = await _get_match(pk)
    except tracker.models.Match.DoesNotExist:
        if request.headers.get("HX-Request") == "true":
            response = HttpResponse()
            response["HX-Redirect"] = reverse("match-list")
            return response
        return await _not_found_response(request)
    user = await request.auser()
    request.user = user
    return render(
        request,
        "tracker/partials/match_detail_content.html",
        await _match_detail_context(match, can_modify=user.is_authenticated),
    )


@login_required
async def match_edit(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        match = await _get_match(pk)
    except tracker.models.Match.DoesNotExist:
        return await _not_found_response(request)
    return redirect("match-detail", pk=match.pk)


@login_required
async def match_field_edit(
    request: HttpRequest, pk: int, field_name: str
) -> HttpResponse:
    if field_name not in MATCH_EDIT_FIELDS:
        return await _not_found_response(request)
    try:
        match = await _get_match(pk)
    except tracker.models.Match.DoesNotExist:
        return await _not_found_response(request)
    request.user = await request.auser()
    if request.GET.get("cancel") == "1":
        if request.headers.get("HX-Request") == "true":
            return render(
                request,
                "tracker/partials/match_detail_row.html",
                {
                    "match": match,
                    "can_modify": True,
                    "field_name": field_name,
                    "field_label": MATCH_EDIT_LABELS[field_name],
                },
            )
        return redirect("match-detail", pk=match.pk)
    form_field_name = MATCH_EDIT_FIELDS[field_name]
    form = tracker.forms.MatchForm(
        request.POST or None, instance=match, editable_field=form_field_name
    )
    await _set_team_choices(form)
    form.fields[form_field_name].widget.attrs["autofocus"] = True
    if request.method == "POST" and await _form_is_valid(form):
        match = await sync_to_async(_save_match_form)(form)
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
                request, "tracker/partials/match_detail_row_saved.html", context
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
            },
        )
    if not form.is_bound:
        return redirect(f"{reverse('match-detail', args=[match.pk])}?edit={field_name}")
    return render(
        request,
        "tracker/match_detail.html",
        await _match_detail_context(
            match, can_modify=True, editing_field=field_name, edit_form=form
        ),
        status=400,
    )


@require_POST
@login_required
async def match_swap_teams(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        match = await _get_match(pk)
    except tracker.models.Match.DoesNotExist:
        return await _not_found_response(request)
    await tracker.models.Match.objects.filter(pk=pk).aupdate(
        home_team=match.away_team,
        away_team=match.home_team,
    )
    await match.score_events.aupdate(
        side=Case(
            When(
                side=tracker.models.ScoreEvent.Side.HOME,
                then=Value(tracker.models.ScoreEvent.Side.AWAY),
            ),
            default=Value(tracker.models.ScoreEvent.Side.HOME),
        )
    )
    return redirect("match-detail", pk=pk)


@require_POST
@login_required
async def match_set_status(request: HttpRequest, pk: int, status: str) -> HttpResponse:
    if status not in tracker.models.Match.Status.values:
        return await _not_found_response(request)
    updated = await tracker.models.Match.objects.filter(pk=pk).aupdate(status=status)
    if not updated:
        return await _not_found_response(request)
    return redirect("match-detail", pk=pk)


@login_required
async def match_delete(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        match = await _get_match(pk)
    except tracker.models.Match.DoesNotExist:
        return await _not_found_response(request)
    if request.method == "POST":
        await match.adelete()
        return redirect("match-list")
    request.user = await request.auser()
    return render(
        request, "tracker/confirm_delete.html", {"object": match, "kind": "match"}
    )


@login_required
async def match_score(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        match = await _get_match(pk)
    except tracker.models.Match.DoesNotExist:
        return await _not_found_response(request)
    return redirect("match-detail", pk=match.pk)


@require_POST
@login_required
async def score_goal(
    request: HttpRequest, pk: int, side: tracker.models.ScoreEvent.Side
) -> HttpResponse:
    try:
        match = await _get_match(pk)
    except tracker.models.Match.DoesNotExist:
        return await _not_found_response(request)
    if match.status not in {
        tracker.models.Match.Status.LIVE,
        tracker.models.Match.Status.FINISHED,
    }:
        return HttpResponseForbidden("Only live or finished matches can be scored.")
    form = tracker.forms.GoalForm(request.POST)
    if not await _form_is_valid(form):
        return HttpResponse("Invalid scorer.", status=400)
    scorer = None
    scorer_name = str(form.cleaned_data["scorer_name"])
    if scorer_name:
        scoring_team = (
            match.home_team
            if side == tracker.models.ScoreEvent.Side.HOME
            else match.away_team
        )
        scorer = await sync_to_async(_get_or_create_player)(scorer_name, scoring_team)
    now = timezone.now()
    await tracker.models.ScoreEvent.objects.acreate(
        match=match, side=side, scorer=scorer, recorded_at=now, occurred_at=now
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
    request: HttpRequest, pk: int, side: tracker.models.ScoreEvent.Side
) -> HttpResponse:
    try:
        match = await _get_match(pk)
    except tracker.models.Match.DoesNotExist:
        return await _not_found_response(request)
    if match.status not in {
        tracker.models.Match.Status.LIVE,
        tracker.models.Match.Status.FINISHED,
    }:
        return HttpResponseForbidden("Only live or finished matches can be scored.")
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
