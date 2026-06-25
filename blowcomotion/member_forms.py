from django import forms

from blowcomotion.models import Instrument, Member

# Choices reused in profile template rendering (mirror MemberSignupForm)
SHIRT_SIZE_CHOICES = [
    ('', 'Select a size'),
    ('S', 'S'),
    ('M', 'M'),
    ('L', 'L'),
    ('XL', 'XL'),
    ('2XL', '2XL'),
    ('3XL', '3XL'),
    ('4XL', '4XL'),
]

DIETARY_CHOICES = [
    ('No Dietary Restrictions', 'No Dietary Restrictions'),
    ('Vegetarian', 'Vegetarian'),
    ('Vegan', 'Vegan'),
    ('Gluten-Free', 'Gluten-Free'),
    ('Dairy-Free / Lactose Intolerance', 'Dairy-Free / Lactose Intolerance'),
    ('Nut-Allergies', 'Nut-Allergies'),
    ('FODMAP Diet', 'FODMAP Diet'),
    ('Ovo-Vegetarian', 'Ovo-Vegetarian'),
    ('Lacto-Vegetarian', 'Lacto-Vegetarian'),
    ('Lacto-Ovo Vegetarians', 'Lacto-Ovo Vegetarians'),
    ('Pescetarians', 'Pescetarians'),
    ('Kosher', 'Kosher'),
    ('Halal', 'Halal'),
    ('Ital', 'Ital'),
    ('Other', 'Other'),
]

ALLERGEN_CHOICES = [
    ('Tree Nut', 'Tree Nut'),
    ('Peanut', 'Peanut'),
    ('Milk', 'Milk'),
    ('Egg', 'Egg'),
    ('Wheat', 'Wheat'),
    ('Soy', 'Soy'),
    ('Fish', 'Fish'),
    ('Shellfish', 'Shellfish'),
    ('Other', 'Other'),
]


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
