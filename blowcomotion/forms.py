from django import forms
from django.forms import formset_factory
from blowcomotion.models import AttendanceRecord, Member, Section


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
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Type of event"
    )
    
    event_name = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Event name (optional for performances)',
            'class': 'form-control'
        }),
        help_text="Optional name for the performance (e.g., 'Summer Concert', 'Holiday Show')"
    )
    
    def __init__(self, section=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.section = section
        
        if section:
            # Get all active members in this section
            member_instruments = section.instrument_set.all().values_list('memberinstrument__member', flat=True)
            section_members = Member.objects.filter(
                id__in=member_instruments,
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
