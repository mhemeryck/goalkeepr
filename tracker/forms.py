import typing

from django import forms

import tracker.models


class MatchForm(forms.ModelForm[tracker.models.Match]):
    is_home = forms.TypedChoiceField(
        label="Venue",
        choices=[(True, "Home"), (False, "Away")],
        coerce=lambda value: value == "True",
        initial=True,
        widget=forms.RadioSelect,
    )

    class Meta:
        model = tracker.models.Match
        fields = ["opponent_name", "match_date", "is_home", "notes"]
        widgets = {
            "match_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["notes"].required = False
