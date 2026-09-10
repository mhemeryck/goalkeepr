import typing

from asgiref.sync import sync_to_async
from django import forms
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Case, Count, Prefetch, Q, QuerySet, Value, When
from django.db.models.deletion import ProtectedError
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
    membership_count: int
    is_default: bool


class ScoredMatch(typing.Protocol):
    home_score_value: int
    away_score_value: int


MATCH_EDIT_FIELDS = {
    "home-team": "home_team",
    "away-team": "away_team",
    "date": "match_date",
    "notes": "notes",
}
MATCH_EDIT_LABELS = {
    "home-team": "Home team",
    "away-team": "Away team",
    "date": "Date",
    "notes": "Notes",
}
SCOREBOARD_FIELDS = frozenset({"home-team", "away-team", "date"})

STATUS_TRANSITIONS = {
    tracker.models.Match.Status.SCHEDULED: {
        tracker.models.Match.Status.LIVE,
        tracker.models.Match.Status.CANCELLED,
    },
    tracker.models.Match.Status.LIVE: {
        tracker.models.Match.Status.FINISHED,
        tracker.models.Match.Status.CANCELLED,
    },
    tracker.models.Match.Status.FINISHED: {tracker.models.Match.Status.LIVE},
    tracker.models.Match.Status.CANCELLED: {tracker.models.Match.Status.SCHEDULED},
}


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
        "away_team__club",
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


async def _match_list_context(request: HttpRequest) -> dict[str, typing.Any]:
    seasons = tracker.models.Season.choices
    defaults = await _defaults()
    default_team = await _resolve_default_team(defaults)
    selected_season = request.GET.get("season")
    if selected_season is None:
        selected_season = (
            str(defaults.default_season)
            if defaults is not None and defaults.default_season is not None
            else "all"
        )
    queryset = tracker.models.Match.objects.all()
    if selected_season != "all":
        season_id: int | None
        try:
            season_id = int(selected_season)
        except ValueError:
            season_id = defaults.default_season if defaults is not None else None
            selected_season = str(season_id) if season_id is not None else "all"
        if season_id is not None:
            if (
                defaults is not None
                and defaults.default_season == season_id
                and default_team is not None
            ):
                queryset = queryset.filter(
                    Q(home_team_id=default_team.pk) | Q(away_team_id=default_team.pk)
                )
            else:
                queryset = queryset.filter(home_team__season=season_id)
    query = request.GET.get("q", "").strip()
    if query:
        match_query = (
            Q(home_team__club__name__icontains=query)
            | Q(away_team__club__name__icontains=query)
            | Q(home_team__age_group__icontains=query)
            | Q(away_team__age_group__icontains=query)
        )
        for season, label in tracker.models.Season.choices:
            if query.casefold() in label.casefold():
                match_query |= Q(home_team__season=season) | Q(away_team__season=season)
        queryset = queryset.filter(match_query)
    selected_status = request.GET.get("status", "")
    if selected_status in tracker.models.Match.Status.values:
        queryset = queryset.filter(status=selected_status)
    else:
        selected_status = ""
    try:
        page = max(int(request.GET.get("page", "1")), 1)
    except ValueError:
        page = 1
    page_size = 20
    offset = (page - 1) * page_size
    matches = [
        match
        async for match in _scored_matches(queryset)[offset : offset + page_size + 1]
    ]
    has_more = len(matches) > page_size
    matches = matches[:page_size]
    params = request.GET.copy()
    params["page"] = str(page + 1)
    return {
        "matches": matches,
        "seasons": seasons,
        "selected_season": selected_season,
        "selected_status": selected_status,
        "query": query,
        "show_team_context": selected_season == "all",
        "next_url": (
            f"{reverse('match-list')}?{params.urlencode()}" if has_more else None
        ),
        "primary_team_id": default_team.pk if default_team is not None else None,
        "primary_club_name": (
            defaults.default_club.name
            if defaults is not None and defaults.default_club is not None
            else "Goalkeepr"
        ),
    }


async def _players(team: tracker.models.Team) -> list[tracker.models.Player]:
    return [
        player
        async for player in tracker.models.Player.objects.filter(teams=team).order_by(
            "name"
        )
    ]


async def _team_choices() -> list[tuple[int, str]]:
    today = timezone.localdate()
    current_season = today.year if today.month >= 7 else today.year - 1
    return [
        (team.pk, f"{team} ({team.get_season_display()})")
        async for team in tracker.models.Team.objects.select_related("club")
        .alias(
            current_season_order=Case(
                When(
                    season=current_season,
                    then=Value(0),
                ),
                default=Value(1),
            )
        )
        .order_by(
            "current_season_order",
            "-season",
            "club__name",
            "age_group",
        )
    ]


async def _team_choices_for_season(season_id: int | None) -> list[tuple[int, str]]:
    if season_id is None:
        return []
    return [
        (team.pk, str(team))
        async for team in tracker.models.Team.objects.filter(
            season=season_id
        ).select_related("club")
    ]


async def _season_choices() -> list[tuple[int, str]]:
    return list(reversed(tracker.models.Season.choices))


async def _club_choices() -> list[tuple[int, str]]:
    return [(club.pk, str(club)) async for club in tracker.models.Club.objects.all()]


async def _set_team_choices(form: tracker.forms.MatchForm) -> None:
    choices = await _team_choices()
    for field_name in ("home_team", "away_team"):
        if field_name in form.fields:
            typing.cast(forms.ChoiceField, form.fields[field_name]).choices = choices


async def _club_names() -> list[str]:
    return [
        name
        async for name in tracker.models.Club.objects.order_by("name").values_list(
            "name", flat=True
        )
    ]


async def _defaults() -> tracker.models.Defaults | None:
    return await tracker.models.Defaults.objects.select_related("default_club").afirst()


async def _resolve_default_team(
    defaults: tracker.models.Defaults | None,
) -> tracker.models.Team | None:
    if (
        defaults is None
        or defaults.default_club_id is None
        or defaults.default_season is None
        or not defaults.default_age_group
    ):
        return None
    return (
        await tracker.models.Team.objects.select_related("club")
        .filter(
            club_id=defaults.default_club_id,
            season=defaults.default_season,
            age_group=defaults.default_age_group,
        )
        .afirst()
    )


async def _opponent_team_choices(
    default_team: tracker.models.Team,
) -> list[tuple[int, str]]:
    teams = tracker.models.Team.objects.select_related("club").exclude(
        pk=default_team.pk
    )
    teams = teams.filter(
        season=default_team.season,
        age_group=default_team.age_group,
    )
    return [
        (team.pk, f"{team.club.name} {team.age_group} · {team.get_season_display()}")
        async for team in teams
    ]


async def _players_with_goal_counts() -> list[tracker.models.Player]:
    return [
        player
        async for player in tracker.models.Player.objects.annotate(
            goal_count=Count("score_events", distinct=True),
            membership_count=Count("memberships", distinct=True),
        ).order_by("name", "pk")
    ]


async def _teams_with_results() -> list[TeamResult]:
    default_team = await _resolve_default_team(await _defaults())
    results = {
        team.pk: TeamResult(
            team=team,
            wins=0,
            draws=0,
            losses=0,
            match_count=0,
            membership_count=team.membership_count,
            is_default=default_team is not None and team.pk == default_team.pk,
        )
        async for team in tracker.models.Team.objects.select_related("club").annotate(
            membership_count=Count("memberships")
        )
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
    correction_mode: bool = False,
    selected_scorer_id: int | None = None,
) -> dict[str, typing.Any]:
    events = [event async for event in match.score_events.select_related("scorer")]
    show_score = match.status in {
        tracker.models.Match.Status.LIVE,
        tracker.models.Match.Status.FINISHED,
    }
    can_score = can_modify and (
        match.status == tracker.models.Match.Status.LIVE
        or (match.status == tracker.models.Match.Status.FINISHED and correction_mode)
    )
    household_side = None
    default_team = await _resolve_default_team(await _defaults())
    if default_team is not None and match.home_team_id == default_team.pk:
        household_side = tracker.models.ScoreEvent.Side.HOME
    elif default_team is not None and match.away_team_id == default_team.pk:
        household_side = tracker.models.ScoreEvent.Side.AWAY
    household_team = (
        match.home_team
        if household_side == tracker.models.ScoreEvent.Side.HOME
        else match.away_team
    )
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
        "household_side": household_side,
        "household_players": (
            await _players(household_team)
            if can_score and household_side is not None
            else []
        ),
        "selected_scorer_id": selected_scorer_id,
        "events": events if show_score else [],
        "can_modify": can_modify,
        "can_score": can_score,
        "correction_mode": correction_mode,
        "show_score": show_score,
    }


async def _match_detail_context(
    match: tracker.models.Match,
    *,
    can_modify: bool,
    editing_field: str | None = None,
    edit_form: tracker.forms.MatchForm | None = None,
    correction_mode: bool = False,
    selected_scorer_id: int | None = None,
) -> dict[str, typing.Any]:
    context = await _score_context(
        match,
        can_modify=can_modify,
        correction_mode=correction_mode,
        selected_scorer_id=selected_scorer_id,
    )
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


def _add_player_to_team(name: str, team: tracker.models.Team) -> tracker.models.Player:
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


def _save_created_match(
    form: tracker.forms.MatchCreateForm,
    default_team: tracker.models.Team,
) -> tracker.models.Match:
    opponent = typing.cast(tracker.models.Team, form.cleaned_data["opponent_team"])
    is_home = form.cleaned_data["is_home"] == "true"
    match = tracker.models.Match(
        home_team=default_team if is_home else opponent,
        away_team=opponent if is_home else default_team,
        match_date=form.cleaned_data["match_date"],
        notes=form.cleaned_data["notes"],
    )
    match.full_clean()
    match.save()
    return match


async def match_list(request: HttpRequest) -> HttpResponse:
    request.user = await request.auser()
    context = await _match_list_context(request)
    if request.headers.get("HX-Request") == "true":
        return render(request, "tracker/partials/match_page.html", context)
    return render(request, "tracker/match_list.html", context)


@login_required
async def player_list(request: HttpRequest) -> HttpResponse:
    request.user = await request.auser()
    return render(
        request,
        "tracker/player_list.html",
        {"players": await _players_with_goal_counts()},
    )


@login_required
async def player_detail(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        player = await tracker.models.Player.objects.aget(pk=pk)
    except tracker.models.Player.DoesNotExist:
        return await _not_found_response(request)
    request.user = await request.auser()
    memberships = [
        membership
        async for membership in tracker.models.TeamMembership.objects.filter(
            player=player
        ).select_related("team__club")
    ]
    events = [
        event
        async for event in tracker.models.ScoreEvent.objects.filter(
            scorer=player
        ).select_related(
            "match__home_team__club",
            "match__away_team__club",
        )
    ]
    return render(
        request,
        "tracker/player_detail.html",
        {"player": player, "memberships": memberships, "events": events},
    )


@login_required
async def player_edit(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        player = await tracker.models.Player.objects.annotate(
            goal_count=Count("score_events", distinct=True),
            membership_count=Count("memberships", distinct=True),
        ).aget(pk=pk)
    except tracker.models.Player.DoesNotExist:
        return await _not_found_response(request)
    request.user = await request.auser()
    form = tracker.forms.PlayerForm(request.POST or None, instance=player)
    if request.method == "POST" and await _form_is_valid(form):
        await sync_to_async(form.save)()
        if request.headers.get("HX-Request") == "true":
            player = await tracker.models.Player.objects.annotate(
                goal_count=Count("score_events", distinct=True),
                membership_count=Count("memberships", distinct=True),
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
    try:
        await player.adelete()
    except ProtectedError:
        return HttpResponse(
            "This player is referenced by retained history.",
            status=409,
        )
    return redirect("player-list")


@login_required
async def team_list(request: HttpRequest) -> HttpResponse:
    request.user = await request.auser()
    return render(
        request, "tracker/team_list.html", {"teams": await _teams_with_results()}
    )


@login_required
async def team_create(request: HttpRequest) -> HttpResponse:
    request.user = await request.auser()
    next_page = request.GET.get("next")
    is_modal = request.headers.get("HX-Request") == "true" and next_page in {
        "match-create",
        "team-list",
        "club-detail",
    }
    club = None
    if club_id := request.GET.get("club"):
        try:
            club = await tracker.models.Club.objects.aget(pk=club_id)
        except tracker.models.Club.DoesNotExist, ValueError:
            pass
    defaults = await _defaults()
    required_context = (
        await _resolve_default_team(defaults) if next_page == "match-create" else None
    )
    initial: dict[str, typing.Any] = {}
    if defaults is not None:
        initial = {
            "club_name": (
                defaults.default_club.name if defaults.default_club is not None else ""
            ),
            "season": defaults.default_season,
            "age_group": defaults.default_age_group,
        }
    if club is not None:
        initial["club_name"] = club.name
    form = tracker.forms.TeamForm(
        request.POST or None,
        initial=initial,
        season_choices=await _season_choices(),
        required_context=required_context,
    )
    if request.method == "POST" and await _form_is_valid(form):
        team = await sync_to_async(form.save)()
        if is_modal and next_page == "match-create" and required_context is not None:
            return render(
                request,
                "tracker/partials/team_created_for_match.html",
                {
                    "opponent_choices": await _opponent_team_choices(required_context),
                    "opponent_team": team,
                },
            )
        if is_modal and next_page in {"team-list", "club-detail"}:
            response = HttpResponse(status=204)
            response["HX-Refresh"] = "true"
            return response
        if next_page == "match-create":
            return redirect(f"{reverse('match-create')}?opponent={team.pk}")
        if next_page == "club-detail" and club is not None:
            return redirect("club-detail", pk=club.pk)
        return redirect("team-detail", pk=team.pk)
    template_name = (
        "tracker/partials/team_form_modal.html"
        if is_modal
        else "tracker/team_form.html"
    )
    return render(
        request,
        template_name,
        {
            "form": form,
            "title": "Add opponent team" if next_page == "match-create" else "Add team",
            "is_modal": is_modal,
            "cancel_url": (
                reverse("match-create")
                if next_page == "match-create"
                else (
                    reverse("club-detail", args=[club.pk])
                    if next_page == "club-detail" and club is not None
                    else reverse("team-list")
                )
            ),
            "club_names": await _club_names(),
        },
        status=400 if form.is_bound else 200,
    )


@login_required
async def team_detail(request: HttpRequest, pk: int) -> HttpResponse:
    result = await _team_result(pk)
    if result is None:
        return await _not_found_response(request)
    request.user = await request.auser()
    team = result["team"]
    memberships = [
        membership
        async for membership in tracker.models.TeamMembership.objects.filter(
            team=team
        ).select_related("player")
    ]
    matches = [
        match
        async for match in _scored_matches(
            tracker.models.Match.objects.filter(Q(home_team=team) | Q(away_team=team))
        )
    ]
    return render(
        request,
        "tracker/team_detail.html",
        {
            "result": result,
            "team": team,
            "memberships": memberships,
            "matches": matches,
            "primary_team_id": (
                default_team.pk
                if (default_team := await _resolve_default_team(await _defaults()))
                else None
            ),
            "show_team_context": False,
        },
    )


@login_required
async def club_list(request: HttpRequest) -> HttpResponse:
    request.user = await request.auser()
    clubs = [
        club
        async for club in tracker.models.Club.objects.prefetch_related(
            Prefetch(
                "teams",
                queryset=tracker.models.Team.objects.order_by("-season", "age_group"),
                to_attr="seasonal_teams",
            )
        )
    ]
    return render(request, "tracker/club_list.html", {"clubs": clubs})


@login_required
async def club_create(request: HttpRequest) -> HttpResponse:
    request.user = await request.auser()
    form = tracker.forms.ClubForm(request.POST or None)
    if request.method == "POST" and await _form_is_valid(form):
        club = await sync_to_async(form.save)()
        return redirect("club-detail", pk=club.pk)
    return render(
        request,
        "tracker/club_form.html",
        {"form": form, "title": "Add club"},
        status=400 if form.is_bound else 200,
    )


@login_required
async def club_detail(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        club = await tracker.models.Club.objects.prefetch_related(
            Prefetch(
                "teams",
                queryset=tracker.models.Team.objects.order_by("-season", "age_group"),
                to_attr="seasonal_teams",
            )
        ).aget(pk=pk)
    except tracker.models.Club.DoesNotExist:
        return await _not_found_response(request)
    request.user = await request.auser()
    return render(
        request,
        "tracker/club_detail.html",
        {"club": club, "can_delete": not club.seasonal_teams},
    )


@login_required
async def club_edit(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        club = await tracker.models.Club.objects.aget(pk=pk)
    except tracker.models.Club.DoesNotExist:
        return await _not_found_response(request)
    request.user = await request.auser()
    form = tracker.forms.ClubForm(request.POST or None, instance=club)
    if request.method == "POST" and await _form_is_valid(form):
        await sync_to_async(form.save)()
        return redirect("club-detail", pk=club.pk)
    return render(
        request,
        "tracker/club_form.html",
        {"club": club, "form": form, "title": "Edit club"},
        status=400 if form.is_bound else 200,
    )


@login_required
async def club_delete(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        club = await tracker.models.Club.objects.aget(pk=pk)
    except tracker.models.Club.DoesNotExist:
        return await _not_found_response(request)
    request.user = await request.auser()
    if await club.teams.aexists():
        return HttpResponse(
            "This club has teams. Reassign or delete every team before "
            "deleting the club.",
            status=409,
        )
    if request.method == "POST":
        try:
            await club.adelete()
        except ProtectedError:
            return HttpResponse(
                "This club is required by application defaults.",
                status=409,
            )
        return redirect("club-list")
    return render(request, "tracker/club_confirm_delete.html", {"club": club})


@login_required
async def defaults_edit(request: HttpRequest) -> HttpResponse:
    request.user = await request.auser()
    defaults, _ = await tracker.models.Defaults.objects.aget_or_create(pk=1)
    form = tracker.forms.DefaultsForm(
        request.POST or None,
        instance=defaults,
        club_choices=await _club_choices(),
        season_choices=await _season_choices(),
    )
    if request.method == "POST" and await _form_is_valid(form):
        await sync_to_async(_save_defaults_form)(form)
        return redirect("match-list")
    return render(
        request,
        "tracker/defaults_form.html",
        {"form": form},
        status=400 if form.is_bound else 200,
    )


def _save_defaults_form(form: tracker.forms.DefaultsForm) -> tracker.models.Defaults:
    defaults = form.save(commit=False)
    defaults.full_clean()
    defaults.save()
    return defaults


@login_required
async def team_edit(request: HttpRequest, pk: int) -> HttpResponse:
    result = await _team_result(pk)
    if result is None:
        return await _not_found_response(request)
    request.user = await request.auser()
    team = result["team"]
    form = tracker.forms.TeamForm(
        request.POST or None,
        instance=team,
        season_choices=await _season_choices(),
    )
    if request.method == "POST" and await _form_is_valid(form):
        await sync_to_async(form.save)()
        return redirect("team-detail", pk=team.pk)
    return render(
        request,
        "tracker/team_form.html",
        {
            "team": team,
            "title": "Edit team",
            "form": form,
            "cancel_url": reverse("team-detail", args=[team.pk]),
            "club_names": await _club_names(),
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
    if await tracker.models.Match.objects.filter(
        Q(home_team=team) | Q(away_team=team)
    ).aexists():
        return HttpResponse("This team is used in matches.", status=409)
    try:
        await team.adelete()
    except ProtectedError:
        return HttpResponse(
            "This team is referenced by retained history or application defaults.",
            status=409,
        )
    return redirect("team-list")


@login_required
async def match_create(request: HttpRequest) -> HttpResponse:
    request.user = await request.auser()
    defaults = await _defaults()
    if (
        defaults is None
        or defaults.default_club is None
        or defaults.default_season is None
        or not defaults.default_age_group
    ):
        return HttpResponse(
            "Configure default club, season, and age group before adding a match. "
            f'<a href="{reverse("defaults-edit")}">Configure defaults</a>.',
            status=409,
        )
    default_team = await _resolve_default_team(defaults)
    if default_team is None:
        return HttpResponse(
            "The configured defaults do not identify an existing household team. "
            f'<a href="{reverse("defaults-edit")}">Configure defaults</a>.',
            status=409,
        )
    opponent_choices = await _opponent_team_choices(default_team)
    form = tracker.forms.MatchCreateForm(
        request.POST or None,
        default_team=default_team,
        opponent_choices=opponent_choices,
        initial={"opponent_team": request.GET.get("opponent", "")},
    )
    if request.method == "POST" and await _form_is_valid(form):
        match = await sync_to_async(_save_created_match)(form, default_team)
        return redirect("match-detail", pk=match.pk)
    return render(
        request,
        "tracker/form.html",
        {
            "form": form,
            "title": "Add match",
            "default_team": default_team,
        },
        status=400 if form.is_bound else 200,
    )


async def _get_match(pk: int) -> tracker.models.Match:
    return await tracker.models.Match.objects.select_related(
        "home_team__club", "away_team__club"
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
    try:
        selected_scorer_id = int(request.GET.get("scorer", ""))
    except ValueError:
        selected_scorer_id = None
    return render(
        request,
        "tracker/match_detail.html",
        await _match_detail_context(
            match,
            can_modify=user.is_authenticated,
            editing_field=editing_field,
            edit_form=edit_form,
            correction_mode=request.GET.get("correct") == "1",
            selected_scorer_id=selected_scorer_id,
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


async def match_scoreboard_fragment(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        match = await _get_match(pk)
    except tracker.models.Match.DoesNotExist:
        response = HttpResponse()
        response["HX-Redirect"] = reverse("match-list")
        return response
    user = await request.auser()
    request.user = user
    return render(
        request,
        "tracker/partials/scoreboard.html",
        await _score_context(match, can_modify=user.is_authenticated),
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
    try:
        match = await tracker.models.Match.objects.aget(pk=pk)
    except tracker.models.Match.DoesNotExist:
        return await _not_found_response(request)
    current_status = tracker.models.Match.Status(match.status)
    target_status = tracker.models.Match.Status(status)
    if target_status not in STATUS_TRANSITIONS[current_status]:
        return HttpResponse("Invalid match status transition.", status=409)
    match.status = target_status
    await match.asave(update_fields=["status", "updated_at"])
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
    if (
        match.status == tracker.models.Match.Status.FINISHED
        and request.POST.get("correction") != "1"
    ):
        return HttpResponseForbidden("Enter correction mode to change a final result.")
    scorer = None
    scoring_team = (
        match.home_team
        if side == tracker.models.ScoreEvent.Side.HOME
        else match.away_team
    )
    default_team = await _resolve_default_team(await _defaults())
    if default_team is not None and scoring_team.pk == default_team.pk:
        players = await _players(scoring_team)
        form = tracker.forms.GoalForm(
            request.POST,
            team=scoring_team,
            player_choices=[(player.pk, player.name) for player in players],
        )
        if not await _form_is_valid(form):
            return HttpResponse("Invalid scorer.", status=400)
        scorer = form.cleaned_data["scorer"]
    now = timezone.now()
    await tracker.models.ScoreEvent.objects.acreate(
        match=match, side=side, scorer=scorer, recorded_at=now, occurred_at=now
    )
    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "tracker/partials/scoreboard.html",
            await _score_context(
                match,
                can_modify=True,
                correction_mode=match.status == tracker.models.Match.Status.FINISHED,
            ),
        )
    return redirect("match-detail", pk=match.pk)


@require_POST
@login_required
async def match_player_add(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        match = await _get_match(pk)
    except tracker.models.Match.DoesNotExist:
        return await _not_found_response(request)
    default_team = await _resolve_default_team(await _defaults())
    household_team = None
    if default_team is not None and match.home_team_id == default_team.pk:
        household_team = match.home_team
    elif default_team is not None and match.away_team_id == default_team.pk:
        household_team = match.away_team
    if household_team is None:
        return HttpResponse("This match has no configured household team.", status=409)
    form = tracker.forms.AddPlayerForm(request.POST)
    if not await _form_is_valid(form):
        return HttpResponse("Enter a player name.", status=400)
    player = await sync_to_async(_add_player_to_team)(
        str(form.cleaned_data["name"]), household_team
    )
    correction_mode = request.POST.get("correction") == "1"
    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "tracker/partials/scoreboard.html",
            await _score_context(
                match,
                can_modify=True,
                correction_mode=correction_mode,
                selected_scorer_id=player.pk,
            ),
        )
    params = f"?scorer={player.pk}"
    if correction_mode:
        params += "&correct=1"
    return redirect(f"{reverse('match-detail', args=[match.pk])}{params}")


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
    if (
        match.status == tracker.models.Match.Status.FINISHED
        and request.POST.get("correction") != "1"
    ):
        return HttpResponseForbidden("Enter correction mode to change a final result.")
    event = await tracker.models.ScoreEvent.objects.filter(
        match=match, side=side
    ).afirst()
    if event is not None:
        await event.adelete()
    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "tracker/partials/scoreboard.html",
            await _score_context(
                match,
                can_modify=True,
                correction_mode=match.status == tracker.models.Match.Status.FINISHED,
            ),
        )
    return redirect("match-detail", pk=match.pk)
