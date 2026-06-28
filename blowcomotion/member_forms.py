from django import forms
from django.db.models import Count, Exists, OuterRef, Q

from blowcomotion.forms import MemberSignupForm
from blowcomotion.models import Instrument, LibraryInstrument, Member

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
        queryset=Instrument.objects.filter(hide_from_member_forms=False).order_by("name"),
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
        self.fields["primary_instrument"].queryset = Instrument.objects.filter(
            hide_from_member_forms=False
        ).order_by("name")
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


class InstrumentRentalRequestForm(forms.Form):
    instrument = forms.ModelChoiceField(
        queryset=Instrument.objects.none(),
        empty_label="Select an instrument",
        label="Instrument",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    second_choice = forms.ModelChoiceField(
        queryset=Instrument.objects.none(),
        required=False,
        empty_label="No second choice",
        label="Second choice (optional)",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    third_choice = forms.ModelChoiceField(
        queryset=Instrument.objects.none(),
        required=False,
        empty_label="No third choice",
        label="Third choice (optional)",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    notes = forms.CharField(
        required=False,
        label="Notes",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
    policy_acknowledged = forms.BooleanField(
        required=True,
        label="I have read and agree to the Instrument Lending Policy",
        error_messages={"required": "You must acknowledge the policy to submit this request."},
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_qs = Instrument.objects.filter(hide_from_rental=False).annotate(
            available_count=Count(
                "library_inventory",
                filter=(Q(library_inventory__hide_from_rental=False) & Q(library_inventory__status=LibraryInstrument.STATUS_AVAILABLE)),
            )
        )
        has_visible_inventory = LibraryInstrument.objects.filter(instrument=OuterRef("pk"), hide_from_rental=False)
        qs_first = base_qs.filter(Exists(has_visible_inventory)).order_by("name")
        qs_optional = base_qs.order_by("name")

        def label_fn(obj):
            return (
                f"{obj.name} ({obj.available_count} available)"
                if obj.available_count > 0
                else f"{obj.name} (waitlist — 0 available)"
            )

        self.fields["instrument"].queryset = qs_first
        self.fields["instrument"].label_from_instance = label_fn
        for field_name in ("second_choice", "third_choice"):
            self.fields[field_name].queryset = qs_optional
            self.fields[field_name].label_from_instance = label_fn
