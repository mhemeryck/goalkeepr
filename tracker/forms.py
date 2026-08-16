from typing import Any

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
        fields = ["opponent_name", "match_date", "is_home", "location", "notes"]
        widgets = {
            "match_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["location"].required = False
        self.fields["notes"].required = False

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean() or {}
        if cleaned_data.get("is_home"):
            cleaned_data["location"] = ""
        return cleaned_data
