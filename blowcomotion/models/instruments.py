import datetime

from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel
from wagtail.models import DraftStateMixin, LockableMixin, Orderable, RevisionMixin
from wagtail.search import index

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class InstrumentStorageLocation(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    street_address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    state = models.CharField(max_length=255, blank=True, null=True)
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class LibraryInstrument(DraftStateMixin, RevisionMixin, LockableMixin, ClusterableModel, index.Indexed):
    """Track each physical instrument in the Blowcomotion inventory."""

    STATUS_AVAILABLE = "available"
    STATUS_RENTED = "rented"
    STATUS_NEEDS_REPAIR = "needs_repair"
    STATUS_OUT_FOR_REPAIR = "out_for_repair"
    STATUS_DISPOSED = "disposed"

    STATUS_CHOICES = [
        (STATUS_AVAILABLE, "Available"),
        (STATUS_RENTED, "Rented"),
        (STATUS_NEEDS_REPAIR, "Needs Repair/Unplayable"),
        (STATUS_OUT_FOR_REPAIR, "Out for Repair"),
        (STATUS_DISPOSED, "Disposed"),
    ]

    instrument = models.ForeignKey(
        "blowcomotion.Instrument",
        on_delete=models.PROTECT,
        related_name="library_inventory",
        help_text="Instrument type (e.g. Trombone, Trumpet)",
    )
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default=STATUS_AVAILABLE,
        help_text="Current availability of this instrument",
    )
    serial_number = models.TextField(help_text="Serial number or other identifying marks")
    hide_from_rental = models.BooleanField(
        default=False,
        help_text=(
            "Hide this specific unit from the rental request form. Use when a unit is "
            "damaged, reserved, or otherwise unavailable without removing it from inventory."
        ),
    )
    hide_from_member_forms = models.BooleanField(
        default=False,
        help_text=(
            "Hide this specific unit from member-facing instrument selectors. Use when "
            "a unit should not be visible to members but remains in admin inventory."
        ),
    )
    member = models.ForeignKey(
        "blowcomotion.Member",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rented_instruments",
        help_text="Person currently storing or borrowing this instrument",
    )
    rental_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date the instrument was lent to the current member",
    )
    acquisition_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Original cost of acquiring this instrument",
    )
    current_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Current estimated value of this instrument",
    )
    replacement_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Estimated cost to replace this instrument",
    )
    patreon_active = models.BooleanField(
        default=False,
        help_text="Is the renter currently an active Patreon supporter?",
    )
    patreon_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Monthly Patreon support amount",
    )
    last_nag_sent = models.DateField(
        null=True,
        blank=True,
        help_text="Date the most recent nag email was sent to this renter.",
    )
    storage_location = models.ForeignKey(
        "blowcomotion.InstrumentStorageLocation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stored_instruments",
        help_text="Physical storage location for this instrument (e.g. organization locker). Leave blank if stored with member.",
    )
    comments = models.TextField(
        blank=True,
        null=True,
        help_text="Additional context or maintenance notes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    search_fields = [
        index.SearchField("serial_number"),
        index.SearchField("comments"),
        index.AutocompleteField("serial_number"),
        index.RelatedFields("instrument", [
            index.SearchField("name"),
            index.AutocompleteField("name"),
        ]),
        index.RelatedFields("member", [
            index.SearchField("first_name"),
            index.SearchField("last_name"),
            index.AutocompleteField("first_name"),
            index.AutocompleteField("last_name"),
        ]),
    ]

    class Meta:
        ordering = ["instrument__name", "serial_number"]
        verbose_name = "Library Instrument"
        verbose_name_plural = "Library Instruments"

    def __str__(self):
        status_display = self.get_status_display()
        if self.member:
            return f"{self.instrument.name} ({self.serial_number[:20]}) - {status_display} - {self.member.full_name}"
        return f"{self.instrument.name} ({self.serial_number[:20]}) - {status_display}"

    @property
    def instrument_name(self):
        return self.instrument.name if self.instrument else ""

    def clean(self):
        super().clean()
        if self.status == self.STATUS_RENTED and not self.member:
            raise ValidationError({"member": "Rented instruments must be assigned to a member."})
        # XOR member or storage_location must be set (can't have both or neither)
        if self.member and self.storage_location:
            raise ValidationError("An instrument cannot be stored with a member and in a storage location at the same time. Please choose one or the other.")
        if not self.member and not self.storage_location:
            raise ValidationError("An instrument must be stored with a member or in a storage location. Please choose one.")


    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_status = None
        old_member_id = None
        old_member = None

        if not is_new:
            old_instance = LibraryInstrument.objects.filter(pk=self.pk).first()
            if old_instance:
                old_status = old_instance.status
                old_member_id = old_instance.member_id
                old_member = old_instance.member

        super().save(*args, **kwargs)

        # Update member renting status
        members_to_update = set()

        # If this instrument is rented and has a member, ensure member.renting = True
        if self.status == self.STATUS_RENTED and self.member:
            members_to_update.add(self.member)
            self.member.renting = True
            self.member.save(update_fields=['renting'])

        # If member changed or status changed from rented, check old member's status
        if old_member and old_member != self.member:
            members_to_update.add(old_member)

        # Update old member's renting status if they have no other rentals
        for member in members_to_update:
            if member != self.member:  # Don't recheck current member
                still_renting = LibraryInstrument.objects.filter(
                    member=member,
                    status=self.STATUS_RENTED
                ).exists()
                member.renting = still_renting
                member.save(update_fields=['renting'])

        if is_new:
            InstrumentHistoryLog.objects.create(
                library_instrument=self,
                event_category=InstrumentHistoryLog.EVENT_ACQUISITION,
                event_date=datetime.date.today(),
                notes="Instrument added to library inventory",
            )
            if self.status == self.STATUS_RENTED:
                InstrumentHistoryLog.objects.create(
                    library_instrument=self,
                    event_category=InstrumentHistoryLog.EVENT_OUT_FOR_LOAN,
                    event_date=datetime.date.today(),
                    notes=f"Instrument rented to {self.member.full_name}" if self.member else "Instrument marked as rented",
                )

        if old_status and old_status != self.status:
            if old_status == self.STATUS_RENTED and self.status != self.STATUS_RENTED:
                self.last_nag_sent = None
                # Use update to avoid recursion; save() already called above via super()
                LibraryInstrument.objects.filter(pk=self.pk).update(last_nag_sent=None)
            self._create_status_change_log(old_status, self.status)
        elif (
            self.status == self.STATUS_RENTED
            and old_member_id
            and old_member_id != self.member_id
        ):
            # Member changed without updating status
            InstrumentHistoryLog.objects.create(
                library_instrument=self,
                event_category=InstrumentHistoryLog.EVENT_RETURNED_FROM_LOAN,
                event_date=datetime.date.today(),
                notes=(
                    f"Instrument returned from {old_member.full_name}"
                    if old_member
                    else "Instrument returned from loan"
                ),
            )
            if self.member:
                InstrumentHistoryLog.objects.create(
                    library_instrument=self,
                    event_category=InstrumentHistoryLog.EVENT_OUT_FOR_LOAN,
                    event_date=datetime.date.today(),
                    notes=f"Instrument rented to {self.member.full_name}",
                )

    def _create_status_change_log(self, old_status, new_status):
        status_map = dict(self.STATUS_CHOICES)
        notes = f"Status changed from {status_map.get(old_status)} to {status_map.get(new_status)}"
        event_category = None

        if new_status == self.STATUS_RENTED:
            event_category = InstrumentHistoryLog.EVENT_OUT_FOR_LOAN
            if self.member:
                notes = f"Instrument rented to {self.member.full_name}"
        elif new_status == self.STATUS_AVAILABLE:
            if old_status == self.STATUS_RENTED:
                event_category = InstrumentHistoryLog.EVENT_RETURNED_FROM_LOAN
                notes = "Instrument returned from rental"
            elif old_status == self.STATUS_OUT_FOR_REPAIR:
                event_category = InstrumentHistoryLog.EVENT_RETURNED_FROM_REPAIR
        elif new_status == self.STATUS_OUT_FOR_REPAIR:
            event_category = InstrumentHistoryLog.EVENT_OUT_FOR_REPAIR
            notes = "Instrument sent out for repair"
        elif new_status == self.STATUS_NEEDS_REPAIR:
            event_category = InstrumentHistoryLog.EVENT_LOCATION_CHECK
            notes = "Instrument flagged as needing repair/unplayable"
        elif new_status == self.STATUS_DISPOSED:
            event_category = InstrumentHistoryLog.EVENT_DISPOSAL

        if event_category:
            InstrumentHistoryLog.objects.create(
                library_instrument=self,
                event_category=event_category,
                event_date=datetime.date.today(),
                notes=notes,
            )

    @property
    def renter_inactive(self):
        if self.status != self.STATUS_RENTED or not self.member or not self.member.last_seen:
            return False
        return (datetime.date.today() - self.member.last_seen).days >= 21 or not self.member.is_active


class LibraryInstrumentPhoto(Orderable):
    library_instrument = ParentalKey(
        "blowcomotion.LibraryInstrument",
        related_name="photos",
        on_delete=models.CASCADE,
    )
    image = models.ForeignKey(
        "blowcomotion.CustomImage",
        on_delete=models.CASCADE,
        related_name="+",
    )
    caption = models.CharField(max_length=255, blank=True)

    panels = [
        FieldPanel("image"),
        FieldPanel("caption"),
    ]

    def __str__(self):
        return f"Photo for {self.library_instrument}"


class InstrumentRentalNagLog(models.Model):
    library_instrument = models.ForeignKey(
        "blowcomotion.LibraryInstrument",
        on_delete=models.CASCADE,
        related_name="nag_logs",
    )
    member_name = models.CharField(max_length=255)
    member_email = models.EmailField()
    reasons = models.CharField(
        max_length=255,
        help_text='Comma-separated trigger reasons: "attendance", "patreon", or "attendance+patreon"',
    )
    sent_at = models.DateField()

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return f"{self.member_name} — {self.sent_at} ({self.reasons})"


class InstrumentHistoryLog(models.Model):
    """
    Model for tracking the event history of library instruments.
    Auto-populated when status changes, but can also be manually created.
    """

    # Event category choices
    EVENT_ACQUISITION = 'acquisition'
    EVENT_OUT_FOR_REPAIR = 'out_for_repair'
    EVENT_RETURNED_FROM_REPAIR = 'returned_from_repair'
    EVENT_OUT_FOR_LOAN = 'out_for_loan'
    EVENT_RETURNED_FROM_LOAN = 'returned_from_loan'
    EVENT_LOCATION_CHECK = 'location_check'
    EVENT_DISPOSAL = 'disposal'
    EVENT_RENTAL_NOTE = 'rental_note'
    EVENT_RETURN_NOTE = 'return_note'

    EVENT_CHOICES = [
        (EVENT_ACQUISITION, 'Acquisition'),
        (EVENT_OUT_FOR_REPAIR, 'Out for Repair'),
        (EVENT_RETURNED_FROM_REPAIR, 'Returned from Repair'),
        (EVENT_OUT_FOR_LOAN, 'Out for Loan'),
        (EVENT_RETURNED_FROM_LOAN, 'Returned from Loan'),
        (EVENT_LOCATION_CHECK, 'Location Check'),
        (EVENT_RENTAL_NOTE, 'Rental Note'),
        (EVENT_RETURN_NOTE, 'Return Note'),
        (EVENT_DISPOSAL, 'Disposal'),
    ]

    library_instrument = ParentalKey(
        'blowcomotion.LibraryInstrument',
        on_delete=models.CASCADE,
        related_name='history_logs'
    )
    event_date = models.DateField(
        default=datetime.date.today,
        help_text='Date of this event'
    )
    event_category = models.CharField(
        max_length=50,
        choices=EVENT_CHOICES,
        help_text='Type of event'
    )
    notes = models.TextField(
        blank=True,
        help_text='Details about this event'
    )
    user = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text='User who created this log entry'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    panels = [
        FieldPanel('event_date'),
        FieldPanel('event_category'),
        FieldPanel('notes'),
        FieldPanel('user'),
    ]

    class Meta:
        ordering = ['-event_date', '-created_at']
        verbose_name = 'Instrument History Log'
        verbose_name_plural = 'Instrument History Logs'

    def __str__(self):
        return f"{self.library_instrument.instrument.name} - {self.get_event_category_display()} on {self.event_date}"


class Equipment(ClusterableModel):
    """Track non-instrument physical items in the storeroom (tables, canopy, signs, etc.)."""

    STATUS_AVAILABLE = "available"
    STATUS_NEEDS_REPAIR = "needs_repair"
    STATUS_DISPOSED = "disposed"

    STATUS_CHOICES = [
        (STATUS_AVAILABLE, "Available"),
        (STATUS_NEEDS_REPAIR, "Needs Repair"),
        (STATUS_DISPOSED, "Disposed"),
    ]

    name = models.CharField(max_length=255)
    serial_number = models.TextField(blank=True, help_text="Serial number or other identifying marks")
    quantity = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default=STATUS_AVAILABLE,
    )
    storage_location = models.ForeignKey(
        "blowcomotion.InstrumentStorageLocation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="equipment",
        help_text="Where this item is stored (leave blank if location is unknown)",
    )
    acquisition_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Original cost of acquiring this item",
    )
    current_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Current estimated value of this item",
    )
    replacement_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Estimated cost to replace this item",
    )
    notes = models.TextField(blank=True, null=True, help_text="Additional context or maintenance notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]
        verbose_name = "Equipment"
        verbose_name_plural = "Equipment"


class EquipmentPhoto(Orderable):
    equipment = ParentalKey(
        "blowcomotion.Equipment",
        related_name="photos",
        on_delete=models.CASCADE,
    )
    image = models.ForeignKey(
        "blowcomotion.CustomImage",
        on_delete=models.CASCADE,
        related_name="+",
    )
    caption = models.CharField(max_length=255, blank=True)

    panels = [
        FieldPanel("image"),
        FieldPanel("caption"),
    ]

    def __str__(self):
        return f"Photo for {self.equipment}"
