from django import forms

from blowcomotion.forms import MemberSignupForm
from blowcomotion.models import Instrument, Member

SHIRT_SIZE_CHOICES = MemberSignupForm.SHIRT_SIZE_CHOICES
DIETARY_CHOICES = MemberSignupForm.DIETARY_CHOICES
ALLERGEN_CHOICES = MemberSignupForm.ALLERGEN_CHOICES


def _yesno_to_bool(val):
    if val == "yes":
        return True
    if val == "no":
        return False
    return None


class GetAccessForm(forms.Form):
    email = forms.EmailField(
        label="Your member email address",
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "you@example.com"}),
    )


class MemberProfileForm(forms.ModelForm):
    additional_instruments = forms.ModelMultipleChoiceField(
        queryset=Instrument.objects.all().order_by("name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Additional instruments",
    )
    profile_photo = forms.ImageField(required=False, label="Profile Photo")

    class Meta:
        model = Member
        fields = [
            "first_name",
            "last_name",
            "preferred_name",
            "email",
            "phone",
            "address",
            "city",
            "state",
            "zip_code",
            "country",
            "birth_month",
            "birth_day",
            "birth_year",
            "emergency_contact",
            "bio",
            "inspired_by",
            "primary_instrument",
            "notify_rental_updates",
            "notify_reminders",
            "notify_announcements",
        ]
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 4}),
            "emergency_contact": forms.Textarea(attrs={"rows": 2}),
            "inspired_by": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["additional_instruments"].initial = list(
                self.instance.additional_instruments.values_list("instrument_id", flat=True)
            )
        for field in self.fields.values():
            if not hasattr(field.widget, "attrs"):
                continue
            if isinstance(field.widget, forms.CheckboxSelectMultiple):
                pass  # styled via .instruments-chooser, no Bootstrap class needed
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            else:
                field.widget.attrs.setdefault("class", "form-control")
