import typing

from django import forms
from django.utils import timezone

import tracker.models


class MatchForm(forms.ModelForm[tracker.models.Match]):
    class Meta:
        model = tracker.models.Match
        fields = ["home_team", "away_team", "match_date", "status", "notes"]
        widgets = {
            "match_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(
        self,
        *args: typing.Any,
        editable_field: str | None = None,
        **kwargs: typing.Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        teams = tracker.models.Team.objects.select_related("club")
        typing.cast(
            forms.ModelChoiceField[tracker.models.Team], self.fields["home_team"]
        ).queryset = teams
        typing.cast(
            forms.ModelChoiceField[tracker.models.Team], self.fields["away_team"]
        ).queryset = teams
        self.fields["notes"].required = False
        if not self.is_bound and self.instance.pk is None:
            self.fields["match_date"].initial = timezone.localdate()
        if editable_field is not None:
            self.fields = {editable_field: self.fields[editable_field]}

    def clean(self) -> dict[str, typing.Any]:
        cleaned_data = super().clean() or {}
        if self.instance.pk is None:
            return cleaned_data
        for field_name, side in (
            ("home_team", tracker.models.ScoreEvent.Side.HOME),
            ("away_team", tracker.models.ScoreEvent.Side.AWAY),
        ):
            team = cleaned_data.get(field_name)
            if team is None:
                continue
            invalid_scorer = (
                tracker.models.ScoreEvent.objects.filter(
                    match=self.instance,
                    side=side,
                    scorer__isnull=False,
                )
                .exclude(scorer__teams=team)
                .exists()
            )
            if invalid_scorer:
                self.add_error(
                    field_name,
                    "Changing this team would invalidate existing scorer attribution.",
                )
        return cleaned_data


class MatchCreateForm(forms.Form):
    opponent_team = forms.CharField(label="Opponent team", widget=forms.Select)
    is_home = forms.ChoiceField(
        label="Venue",
        choices=(("true", "Home"), ("false", "Away")),
        widget=forms.RadioSelect,
        initial="true",
    )
    match_date = forms.DateField(
        label="Date",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        initial=timezone.localdate,
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(
        self,
        *args: typing.Any,
        default_team: tracker.models.Team,
        opponent_choices: list[tuple[int, str]],
        **kwargs: typing.Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.default_team = default_team
        typing.cast(forms.Select, self.fields["opponent_team"].widget).choices = [
            ("", "Select opponent team"),
            *opponent_choices,
        ]

    def clean_opponent_team(self) -> tracker.models.Team:
        value = self.cleaned_data["opponent_team"]
        try:
            team = tracker.models.Team.objects.get(pk=value)
        except tracker.models.Team.DoesNotExist, ValueError:
            raise forms.ValidationError("Select a valid opponent team.") from None
        if team.pk == self.default_team.pk:
            raise forms.ValidationError("The opponent must differ from your team.")
        if (
            team.season != self.default_team.season
            or team.age_group != self.default_team.age_group
        ):
            raise forms.ValidationError(
                "Select a team from the default season and age group."
            )
        return team


class GoalForm(forms.Form):
    scorer = forms.ChoiceField(required=False)

    def __init__(
        self,
        *args: typing.Any,
        team: tracker.models.Team,
        player_choices: list[tuple[int, str]],
        **kwargs: typing.Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.team = team
        typing.cast(forms.ChoiceField, self.fields["scorer"]).choices = [
            ("", "No scorer recorded"),
            *player_choices,
        ]

    def clean_scorer(self) -> tracker.models.Player | None:
        value = self.cleaned_data["scorer"]
        if not value:
            return None
        try:
            return tracker.models.Player.objects.get(pk=value, teams=self.team)
        except tracker.models.Player.DoesNotExist:
            raise forms.ValidationError("Select a player from this team.") from None


class PlayerForm(forms.ModelForm[tracker.models.Player]):
    class Meta:
        model = tracker.models.Player
        fields = ["name"]

    def clean_name(self) -> str:
        return str(self.cleaned_data["name"]).strip()


class ClubForm(forms.ModelForm[tracker.models.Club]):
    class Meta:
        model = tracker.models.Club
        fields = ["name"]

    def clean_name(self) -> str:
        return str(self.cleaned_data["name"]).strip()


class TeamForm(forms.ModelForm[tracker.models.Team]):
    club_name = forms.CharField(label="Club", max_length=100)
    season = forms.ChoiceField()

    class Meta:
        model = tracker.models.Team
        fields = ["season", "age_group"]

    def __init__(
        self,
        *args: typing.Any,
        season_choices: list[tuple[int, str]],
        required_context: tracker.models.Team | None = None,
        **kwargs: typing.Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        typing.cast(forms.ChoiceField, self.fields["season"]).choices = season_choices
        self.fields["club_name"].widget.attrs["list"] = "clubs"
        self.required_context = required_context
        if not self.is_bound and self.instance.pk:
            self.fields["club_name"].initial = self.instance.club.name

    def clean_club_name(self) -> str:
        name = str(self.cleaned_data["club_name"]).strip()
        club = tracker.models.Club.objects.filter(name__iexact=name).first()
        if club is not None:
            self.instance.club = club
        return name

    def clean_season(self) -> int:
        try:
            return tracker.models.Season(int(self.cleaned_data["season"])).value
        except TypeError, ValueError:
            raise forms.ValidationError("Select a valid season.") from None

    def clean(self) -> dict[str, typing.Any]:
        cleaned_data = super().clean() or {}
        club_name = cleaned_data.get("club_name")
        season = cleaned_data.get("season")
        age_group = cleaned_data.get("age_group")
        if club_name and season is not None and age_group:
            if self.required_context is not None and (
                season != self.required_context.season
                or age_group != self.required_context.age_group
            ):
                raise forms.ValidationError(
                    "Opponent teams must use the default season and age group."
                )
            duplicate = tracker.models.Team.objects.filter(
                club__name__iexact=club_name,
                season=season,
                age_group=age_group,
            )
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise forms.ValidationError(
                    "This club already has that age group in the selected season."
                )
        return cleaned_data

    def save(self, commit: bool = True) -> tracker.models.Team:
        team = super().save(commit=False)
        if team.club_id is None:
            team.club = tracker.models.Club.objects.create(
                name=self.cleaned_data["club_name"]
            )
        if commit:
            team.save()
        return team


class DefaultsForm(forms.ModelForm[tracker.models.Defaults]):
    default_club = forms.ChoiceField(required=False)
    default_season = forms.ChoiceField(required=False)

    class Meta:
        model = tracker.models.Defaults
        fields = ["default_club", "default_season", "default_age_group"]

    def __init__(
        self,
        *args: typing.Any,
        club_choices: list[tuple[int, str]],
        season_choices: list[tuple[int, str]],
        **kwargs: typing.Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        typing.cast(forms.ChoiceField, self.fields["default_club"]).choices = [
            ("", "No default club"),
            *club_choices,
        ]
        typing.cast(forms.ChoiceField, self.fields["default_season"]).choices = [
            ("", "No default season"),
            *season_choices,
        ]
        typing.cast(forms.ChoiceField, self.fields["default_age_group"]).choices = [
            ("", "No default age group"),
            *tracker.models.AgeGroup.choices,
        ]

    def clean_default_club(self) -> tracker.models.Club | None:
        value = self.cleaned_data["default_club"]
        if not value:
            return None
        try:
            return tracker.models.Club.objects.get(pk=value)
        except tracker.models.Club.DoesNotExist:
            raise forms.ValidationError("Select a valid default club.") from None

    def clean_default_season(self) -> int | None:
        value = self.cleaned_data["default_season"]
        if not value:
            return None
        try:
            return tracker.models.Season(int(value)).value
        except TypeError, ValueError:
            raise forms.ValidationError("Select a valid default season.") from None


class AddPlayerForm(forms.Form):
    name = forms.CharField(max_length=100)

    def clean_name(self) -> str:
        return str(self.cleaned_data["name"]).strip()
