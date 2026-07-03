import datetime

from wagtail.documents import get_document_model
from wagtail.documents.widgets import AdminDocumentChooser

from django import forms
from django.forms import formset_factory
from django.utils import timezone

from blowcomotion.chooser_viewsets import (
    instrument_chooser_viewset,
    library_instrument_available_chooser_viewset,
    member_chooser_viewset,
)
from blowcomotion.models import Instrument, LibraryInstrument, Member
from blowcomotion.utils import validate_birthday


class MemberSignupForm(forms.Form):
    """Form for new members to sign up and enter their profile data"""
    
    # Required fields (matching Member model requirements)
    first_name = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name'
        })
    )
    
    last_name = forms.CharField(
        max_length=255,
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


class LibraryInstrumentRentForm(forms.Form):
    """Quick admin form to rent out a library instrument."""

    instrument = forms.ModelChoiceField(
        queryset=LibraryInstrument.objects.none(),
        required=True,
        label="Instrument",
        widget=library_instrument_available_chooser_viewset.widget_class,
    )
    member = forms.ModelChoiceField(
        queryset=Member.objects.filter(is_active=True).order_by("first_name", "last_name"),
        required=True,
        label="Member",
        help_text="Assign the instrument to an active member",
        widget=member_chooser_viewset.widget_class,
    )
    rental_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Defaults to today if left blank",
    )
    agreement_signed_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Agreement signed",
    )
    rental_document = forms.ModelChoiceField(
        queryset=get_document_model().objects.all(),
        required=False,
        label="Rental document",
        help_text="Optional: Attach a rental agreement or other document",
        widget=AdminDocumentChooser,
    )
    document_description = forms.CharField(
        required=False,
        max_length=255,
        label="Document description",
        help_text="e.g. 'Rental Agreement', 'Receipt'",
    )
    patreon_active = forms.BooleanField(
        required=False,
        initial=False,
        label="Patreon active",
    )
    patreon_amount = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=0,
        label="Patreon monthly amount",
    )
    comments = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Optional notes for this rental",
    )

    def __init__(self, *args, **kwargs):
        instrument_queryset = kwargs.pop("instrument_queryset", None)
        initial_instrument = kwargs.pop("initial_instrument", None)
        super().__init__(*args, **kwargs)

        queryset = instrument_queryset or LibraryInstrument.objects.filter(
            status=LibraryInstrument.STATUS_AVAILABLE
        )
        self.fields["instrument"].queryset = queryset.select_related("instrument")

        if initial_instrument:
            self.fields["instrument"].initial = initial_instrument.pk
            self.fields["instrument"].widget = forms.HiddenInput()

        if not self.is_bound:
            today = timezone.localdate()
            self.fields["rental_date"].initial = today
            self.fields["agreement_signed_date"].initial = today


class LibraryInstrumentReturnForm(forms.Form):
    """Quick admin form to return an instrument to the inventory."""

    instrument = forms.ModelChoiceField(
        queryset=LibraryInstrument.objects.none(),
        required=True,
        label="Instrument",
        widget=forms.HiddenInput(),  # Hidden - will be set via action button
    )
    condition_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Optional condition notes captured at return",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = LibraryInstrument.objects.filter(status=LibraryInstrument.STATUS_RENTED)
        self.fields["instrument"].queryset = queryset.select_related("instrument", "member")
