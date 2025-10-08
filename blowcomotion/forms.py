import datetime

import requests

from django import forms
from django.conf import settings
from django.forms import formset_factory

from blowcomotion.models import AttendanceRecord, Instrument, Member, Section
from blowcomotion.utils import validate_birthday


class AttendanceForm(forms.Form):
    """Form for capturing attendance for a single member or guest"""
    member = forms.ModelChoiceField(
        queryset=Member.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select members who attended"
    )
    guest_name = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Guest name (if not a member)',
            'class': 'form-control'
        })
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 2,
            'placeholder': 'Optional notes',
            'class': 'form-control'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        member = cleaned_data.get('member')
        guest_name = cleaned_data.get('guest_name')
        
        if not member and not guest_name:
            raise forms.ValidationError("Either select a member or enter a guest name")
        
        if member and guest_name:
            raise forms.ValidationError("Cannot select both member and guest name")
        
        return cleaned_data


class SectionAttendanceForm(forms.Form):
    """Form for capturing attendance for an entire section"""
    EVENT_TYPE_CHOICES = [
        ('rehearsal', 'Rehearsal'),
        ('performance', 'Performance'),
    ]
    
    date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        help_text="Date of event"
    )
    
    event_type = forms.ChoiceField(
        choices=EVENT_TYPE_CHOICES,
        initial='rehearsal',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        help_text="Type of event"
    )
    
    gig = forms.ChoiceField(
        choices=[],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        help_text="Select a gig for this performance date (if applicable)"
    )
    
    def __init__(self, section=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.section = section
        
        # Populate gig choices with available gigs
        self._populate_gig_choices()
        
        if section:
            # Get all active members whose primary instrument is in this section
            section_members = Member.objects.filter(
                primary_instrument__section=section,
                is_active=True
            ).distinct().order_by('first_name', 'last_name')
            
            # Create checkbox field for each member
            for member in section_members:
                field_name = f'member_{member.id}'
                self.fields[field_name] = forms.BooleanField(
                    required=False,
                    label=str(member),
                    widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
                )
            
            # Add fields for guests
            for i in range(5):  # Allow up to 5 guests
                guest_field_name = f'guest_{i}'
                self.fields[guest_field_name] = forms.CharField(
                    required=False,
                    max_length=255,
                    widget=forms.TextInput(attrs={
                        'placeholder': f'Guest {i+1} name',
                        'class': 'form-control'
                    })
                )
                
                guest_notes_field_name = f'guest_notes_{i}'
                self.fields[guest_notes_field_name] = forms.CharField(
                    required=False,
                    widget=forms.Textarea(attrs={
                        'rows': 1,
                        'placeholder': f'Notes for guest {i+1}',
                        'class': 'form-control'
                    })
                )

    def _populate_gig_choices(self):
        """Populate gig choices from GigoGig API"""
        try:
            # Fetch gigs from API
            response = requests.get(
                f"{settings.GIGO_API_URL}/gigs",
                headers={"X-API-KEY": settings.GIGO_API_KEY},
                timeout=5
            )
            response.raise_for_status()
            
            gigs_data = response.json()
            if gigs_data.get("gigs"):
                # Filter gigs: confirmed, blowcomotion band, future dates
                today = datetime.date.today().isoformat()
                filtered_gigs = [
                    gig for gig in gigs_data["gigs"]
                    if (gig.get("date", "") >= today and 
                        gig.get("gig_status", "").lower() == "confirmed" and 
                        gig.get("band", "").lower() == "blowcomotion")
                ]
                
                # Sort by date
                filtered_gigs.sort(key=lambda g: g.get("date", ""))
                
                # Create choices list
                choices = [('', 'No specific gig selected')]
                for gig in filtered_gigs:
                    gig_date = gig.get("date", "")
                    gig_title = gig.get("title", "Untitled Gig")
                    choice_label = f"{gig_date} - {gig_title}"
                    choices.append((gig["id"], choice_label))
                
                self.fields['gig'].choices = choices
            else:
                self.fields['gig'].choices = [('', 'No gigs available')]
                
        except Exception as e:
            # Fallback if API is unavailable
            self.fields['gig'].choices = [('', 'Unable to load gigs')]


class AttendanceReportFilterForm(forms.Form):
    """Form for filtering attendance reports"""
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    section = forms.ModelChoiceField(
        queryset=Section.objects.all(),
        required=False,
        empty_label="All Sections",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    member = forms.ModelChoiceField(
        queryset=Member.objects.filter(is_active=True).order_by('first_name', 'last_name'),
        required=False,
        empty_label="All Members",
        widget=forms.Select(attrs={'class': 'form-control'})
    )


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
        queryset=Instrument.objects.all().order_by('name'),
        required=False,
        empty_label='Select your instrument',
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        help_text='Select the instrument you play (optional)'
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
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email address'
        })
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
    
    def clean(self):
        cleaned_data = super().clean()
        birth_month = cleaned_data.get('birth_month')
        birth_day = cleaned_data.get('birth_day')
        
        # Validate birthday using shared utility function
        validate_birthday(birth_day, birth_month)
        
        return cleaned_data
