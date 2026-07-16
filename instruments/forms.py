from wagtail.documents import get_document_model
from wagtail.documents.widgets import AdminDocumentChooser

from django import forms
from django.utils import timezone

from blowcomotion.chooser_viewsets import (
    library_instrument_available_chooser_viewset,
    member_chooser_viewset,
)
from blowcomotion.models import LibraryInstrument, Member


class LibraryInstrumentRentForm(forms.Form):
    """Quick admin form to rent out a library instrument."""

    instrument = forms.ModelChoiceField(
        queryset=LibraryInstrument.objects.none(),
        required=True,
        label="Instrument",
        widget=library_instrument_available_chooser_viewset.widget_class,
    )
    member = forms.ModelChoiceField(
        queryset=Member.objects.filter(is_active=True).select_related("user").order_by("user__first_name", "user__last_name"),
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
