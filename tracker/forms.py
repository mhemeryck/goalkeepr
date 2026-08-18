import typing

from django import forms
from django.utils import timezone

import tracker.models


class MatchForm(forms.ModelForm[tracker.models.Match]):
    opponent_name = forms.CharField(
        label="Opponent",
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "list": "opponent-teams",
                "autocomplete": "off",
                "aria-describedby": "opponent-help",
            }
        ),
    )
    is_home = forms.TypedChoiceField(
        label="Venue",
        choices=[(True, "Home"), (False, "Away")],
        coerce=lambda value: value == "True",
        initial=True,
        widget=forms.RadioSelect,
    )

    class Meta:
        model = tracker.models.Match
        fields = ["match_date", "is_home", "notes"]
        widgets = {
            "match_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["notes"].required = False
        if not self.is_bound and self.instance.pk is None:
            self.fields["match_date"].initial = timezone.localdate()
        elif not self.is_bound and self.instance.pk is not None:
            self.fields["opponent_name"].initial = self.instance.opponent.name

    def clean_opponent_name(self) -> str:
        return str(self.cleaned_data["opponent_name"]).strip()


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
