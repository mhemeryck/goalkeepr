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
        teams = tracker.models.Team.objects.select_related("club", "season")
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
    opponent_name = forms.CharField(label="Opponent", max_length=100)
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
        **kwargs: typing.Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.default_team = default_team
        self.fields["opponent_name"].widget.attrs["list"] = "opponent-teams"

    def clean_opponent_name(self) -> str:
        name = str(self.cleaned_data["opponent_name"]).strip()
        if name.casefold() == self.default_team.club.name.casefold():
            raise forms.ValidationError("The opponent must differ from your team.")
        return name


class GoalForm(forms.Form):
    scorer_name = forms.CharField(required=False, max_length=100)

    def clean_scorer_name(self) -> str:
        return str(self.cleaned_data["scorer_name"]).strip()


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

    class Meta:
        model = tracker.models.Team
        fields = ["age_group"]

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["age_group"].widget.attrs["list"] = f"age-groups-{self.instance.pk}"
        self.fields["club_name"].widget.attrs["list"] = f"clubs-{self.instance.pk}"
        if not self.is_bound and self.instance.pk:
            self.fields["club_name"].initial = self.instance.club.name

    def clean_club_name(self) -> str:
        name = str(self.cleaned_data["club_name"]).strip()
        club = tracker.models.Club.objects.filter(name__iexact=name).first()
        if club is None:
            raise forms.ValidationError("Select an existing club.")
        self.instance.club = club
        return club.name

    def save(self, commit: bool = True) -> tracker.models.Team:
        team = super().save(commit=False)
        if commit:
            team.save()
        return team


class DefaultsForm(forms.ModelForm[tracker.models.Defaults]):
    default_season = forms.ChoiceField(required=False)
    default_team = forms.ChoiceField(required=False)

    class Meta:
        model = tracker.models.Defaults
        fields = ["default_season", "default_team"]

    def __init__(
        self,
        *args: typing.Any,
        season_choices: list[tuple[int, str]],
        team_choices: list[tuple[int, str]],
        **kwargs: typing.Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        typing.cast(forms.ChoiceField, self.fields["default_season"]).choices = [
            ("", "No default season"),
            *season_choices,
        ]
        typing.cast(forms.ChoiceField, self.fields["default_team"]).choices = [
            ("", "No default team"),
            *team_choices,
        ]

    def clean_default_season(self) -> tracker.models.Season | None:
        value = self.cleaned_data["default_season"]
        if not value:
            return None
        try:
            return tracker.models.Season.objects.get(pk=value)
        except tracker.models.Season.DoesNotExist:
            raise forms.ValidationError("Select a valid default season.") from None

    def clean_default_team(self) -> tracker.models.Team | None:
        value = self.cleaned_data["default_team"]
        if not value:
            return None
        try:
            return tracker.models.Team.objects.get(pk=value)
        except tracker.models.Team.DoesNotExist:
            raise forms.ValidationError("Select a valid default team.") from None

    def clean(self) -> dict[str, typing.Any]:
        cleaned_data = super().clean() or {}
        default_season = cleaned_data.get("default_season")
        default_team = cleaned_data.get("default_team")
        if (
            default_season is not None
            and default_team is not None
            and default_team.season_id != default_season.pk
        ):
            self.add_error(
                "default_team", "The default team must belong to the default season."
            )
        return cleaned_data
