import datetime

from django.core.exceptions import ValidationError
from django.db import models


class AttendanceRecord(models.Model):
    """
    Model for tracking attendance at practice sessions
    
    Attributes:
        date: DateField - date of practice
        member: ForeignKey - reference to Member (nullable for guests)
        guest_name: CharField - name of guest if not a member
        notes: TextField - optional notes about attendance
        created_at: DateTimeField - when record was created
    """

    date = models.DateField(default=datetime.date.today)
    member = models.ForeignKey(
        "blowcomotion.Member",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attendance_records"
    )
    played_instrument = models.ForeignKey(
        "blowcomotion.Instrument",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attendance_records_as_played",
        help_text="Instrument the member played for this attendance entry"
    )
    guest_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Name of guest/visitor (leave blank for members)"
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['date', 'member']
        ordering = ['-date', 'member__last_name']

    def clean(self):
        if not self.member and not self.guest_name:
            raise ValidationError("Either member or guest_name must be provided")
        if self.member and self.guest_name:
            raise ValidationError("Cannot specify both member and guest_name")

    def __str__(self):
        if self.member:
            instrument_label = f" ({self.played_instrument.name})" if self.played_instrument else ""
            return f"{self.member}{instrument_label} - {self.date}"
        else:
            return f"{self.guest_name} (Guest) - {self.date}"
