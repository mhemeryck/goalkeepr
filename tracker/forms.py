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


class TeamForm(forms.ModelForm[tracker.models.Team]):
    club_name = forms.CharField(label="Club", max_length=100)

    class Meta:
        model = tracker.models.Team
        fields = ["age_group", "designation"]

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["age_group"].widget.attrs["list"] = "age-groups"
        if not self.is_bound and self.instance.pk:
            self.fields["club_name"].initial = self.instance.club.name

    def clean_club_name(self) -> str:
        name = str(self.cleaned_data["club_name"]).strip()
        duplicate = tracker.models.Club.objects.filter(name__iexact=name).exclude(
            pk=self.instance.club_id
        )
        if duplicate.exists():
            raise forms.ValidationError("A club with this name already exists.")
        return name

    def save(self, commit: bool = True) -> tracker.models.Team:
        team = super().save(commit=False)
        team.club.name = str(self.cleaned_data["club_name"])
        if commit:
            team.club.save(update_fields=["name"])
            team.save()
        return team
