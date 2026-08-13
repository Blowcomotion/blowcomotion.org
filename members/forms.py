import datetime

from django import forms
from django.db.models import Count, Exists, OuterRef, Q
from django.forms import formset_factory

from blowcomotion.chooser_viewsets import instrument_chooser_viewset
from blowcomotion.models import Instrument, LibraryInstrument, Member
from members.utils import validate_birthday


class MemberSignupForm(forms.Form):
    """Form for new members to sign up and enter their profile data"""
    
    # Required fields (stored on the linked auth User; max_length matches auth_user columns)
    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name'
        })
    )

    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name'
        })
    )
    
    # Instrument selection
    primary_instrument = forms.ModelChoiceField(
        queryset=Instrument.objects.filter(hide_from_member_forms=False).order_by('name'),
        required=True,
        empty_label='Select your instrument',
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        help_text='Select the instrument you play'
    )
    
    # Optional personal information
    preferred_name = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Preferred name (if different from first name)'
        }),
        help_text='Name you prefer to be called (optional)'
    )
    
    # Birthday fields
    birth_month = forms.ChoiceField(
        choices=[('', 'Month')] + [(i, datetime.date(2000, i, 1).strftime('%B')) for i in range(1, 13)],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    birth_day = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=31,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Day (1-31)'
        })
    )
    
    birth_year = forms.IntegerField(
        required=False,
        min_value=1900,
        max_value=datetime.date.today().year,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': f'Year (e.g., {datetime.date.today().year - 30})'
        })
    )
    
    # Contact information
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email address'
        }),
        help_text='Required for gig-o-matic invitation'
    )
    
    phone = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Phone number'
        })
    )
    
    # Address information
    address = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Street address'
        })
    )
    
    city = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'City'
        })
    )
    
    state = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'State'
        })
    )
    
    zip_code = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ZIP code'
        })
    )
    
    country = forms.CharField(
        max_length=255,
        required=False,
        initial='USA',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Country'
        })
    )
    
    # Emergency contact
    emergency_contact = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Emergency contact name and phone number'
        }),
        help_text='Name and phone number of emergency contact'
    )
    
    # Custom field for inspiration
    inspired_by = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Tell us what event or person inspired you to join the band'
        }),
        label='What inspired you to join?',
        help_text='Share what event or person inspired you to join Blowcomotion'
    )

    # Shirt size
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
    shirt_size = forms.ChoiceField(
        choices=SHIRT_SIZE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    # Dietary preferences (multi-select checkboxes)
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
    dietary_preferences = forms.MultipleChoiceField(
        choices=DIETARY_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple()
    )
    dietary_other = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Please describe your dietary preference'
        })
    )

    # Allergy fields
    has_allergies = forms.ChoiceField(
        choices=[('', 'Select'), ('yes', 'Yes'), ('no', 'No')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
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
    allergens = forms.MultipleChoiceField(
        choices=ALLERGEN_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple()
    )
    allergens_other = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Please describe your allergen'
        })
    )
    has_epipen = forms.ChoiceField(
        choices=[('', 'Select'), ('yes', 'Yes'), ('no', 'No')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    allergy_details = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Additional details about your allergies or interventions'
        })
    )
    medical_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Any medical concerns or allergies we should know about'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        birth_month = cleaned_data.get('birth_month')
        birth_day = cleaned_data.get('birth_day')

        # Validate birthday using shared utility function
        validate_birthday(birth_day, birth_month)

        return cleaned_data


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
    # first_name / last_name / email live on the linked auth User (exposed as
    # write-through properties on Member), so they are declared form fields
    # rather than Meta.fields. Names are applied to the instance before model
    # validation so the duplicate-name check sees them; email is handled by
    # the view (held until confirmed via emailed token).
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)

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
            "preferred_name",
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
            self.initial.setdefault("first_name", self.instance.first_name)
            self.initial.setdefault("last_name", self.instance.last_name)
            self.initial.setdefault("email", self.instance.email)
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

    def _post_clean(self):
        # Apply names before model validation so Member.clean()'s duplicate
        # check sees the submitted values. Email is intentionally not applied
        # (the view holds it until the new address is confirmed).
        for field in ("first_name", "last_name"):
            if field in self.cleaned_data:
                setattr(self.instance, field, self.cleaned_data[field])
        super()._post_clean()


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
