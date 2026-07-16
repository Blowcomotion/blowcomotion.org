from django import forms

from blowcomotion.models import Member


class MemberChooserCreationForm(forms.ModelForm):
    """Creation form for the member chooser.

    first_name / last_name / email are write-through properties on Member
    (backed by the linked auth User), not model fields, so they are declared
    here and applied to the instance before validation/save.
    """

    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)

    class Meta:
        model = Member
        fields = [
            "first_name",
            "last_name",
            "email",
            "preferred_name",
            "birth_month",
            "birth_day",
            "birth_year",
            "join_date",
            "is_active",
            "bio",
            "instructor",
            "board_member",
        ]

    def _post_clean(self):
        for field in ("first_name", "last_name", "email"):
            if field in self.cleaned_data:
                setattr(self.instance, field, self.cleaned_data[field])
        super()._post_clean()
