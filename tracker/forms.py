from typing import Any

from django import forms

from tracker.models import Match, Season, Team


class TeamForm(forms.ModelForm[Team]):
    class Meta:
        model = Team
        fields = ["name"]


class SeasonForm(forms.ModelForm[Season]):
    class Meta:
        model = Season
        fields = ["name"]


class MatchForm(forms.ModelForm[Match]):
    is_home = forms.TypedChoiceField(
        label="Venue",
        choices=[(True, "Home"), (False, "Away")],
        coerce=lambda value: value == "True",
        widget=forms.RadioSelect,
    )

    class Meta:
        model = Match
        fields = ["opponent_name", "match_date", "is_home", "location", "notes"]
        widgets = {
            "match_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["location"].required = False
        self.fields["notes"].required = False
