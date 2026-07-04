from django.db import models


class BaseFormSubmission(models.Model):
    """
    Base model for form submissions

    Attributes:
        name: CharField
        email: EmailField
        message: TextField
        date_submitted: DateTimeField
    This is an abstract model that can be inherited by other form submission models.
    """

    name = models.CharField(blank=True, null=True, max_length=255)
    email = models.EmailField(blank=True, null=True, )
    message = models.TextField(blank=True, null=True, )
    date_submitted = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class ContactFormSubmission(BaseFormSubmission):
    """
        Model for contact form submissions
    """
    newsletter_opt_in = models.BooleanField(
        default=False,
        help_text="Whether the user signed up for the newsletter",
    )

    def __str__(self):
        return f"Contact Form Submission from {self.name} on {self.date_submitted}"


class FeedbackFormSubmission(BaseFormSubmission):
    """
        Model for feedback form submissions
    """
    submitted_from_page = models.CharField(
        blank=True,
        null=True,
        max_length=255,
        help_text="The URL of the page from which the feedback was submitted",
    )

    def __str__(self):
        return f"Feedback Form Submission from {self.name} on {self.date_submitted}"


class JoinBandFormSubmission(BaseFormSubmission):
    """
    Model for join band form submissions
    """
    instrument = models.CharField(
        blank=True,
        null=True,
        max_length=255,
        help_text="The instrument the person plays",
    )
    instrument_rental = models.CharField(
        blank=True,
        null=True,
        max_length=10,
        choices=[
            ('yes', 'Yes, I would like to rent an instrument'),
            ('no', 'No, I have my own instrument'),
            ('maybe', 'I\'m not sure yet'),
        ],
        help_text="Whether the person wants to rent an instrument",
    )
    newsletter_opt_in = models.BooleanField(
        default=False,
        help_text="Whether the user signed up for the newsletter",
    )

    def __str__(self):
        return f"Join Band Form Submission from {self.name} on {self.date_submitted}"


class BookingFormSubmission(BaseFormSubmission):
    """
    Model for booking form submissions
    """
    event_date = models.DateField(
        blank=True,
        null=True,
        help_text="Date of the event",
    )
    event_time = models.TimeField(
        blank=True,
        null=True,
        help_text="Time of the event",
    )
    event_location = models.CharField(
        blank=True,
        null=True,
        max_length=500,
        help_text="Location of the event",
    )
    duration = models.CharField(
        blank=True,
        null=True,
        max_length=255,
        help_text="How long the band should play",
    )
    expected_guests = models.CharField(
        blank=True,
        null=True,
        max_length=255,
        help_text="Expected number of guests",
    )
    event_details = models.TextField(
        blank=True,
        null=True,
        help_text="Specific event details and expectations",
    )
    budget = models.CharField(
        blank=True,
        null=True,
        max_length=255,
        help_text="Budget for the performance",
    )
    newsletter_opt_in = models.BooleanField(
        default=False,
        help_text="Whether the user signed up for the newsletter",
    )

    def __str__(self):
        return f"Booking Form Submission from {self.name} on {self.date_submitted}"


class DonateFormSubmission(BaseFormSubmission):
    """
    Model for donate form submissions
    """
    newsletter_opt_in = models.BooleanField(
        default=False,
        help_text="Whether the user signed up for the newsletter",
    )

    def __str__(self):
        return f"Donate Form Submission from {self.name} on {self.date_submitted}"


class InstrumentRentalRequestSubmission(BaseFormSubmission):
    """Member portal instrument rental requests. `message` field stores optional notes."""

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_DENIED = "denied"
    STATUS_RETURNED = "returned"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_DENIED, "Denied"),
        (STATUS_RETURNED, "Returned"),
    ]

    member = models.ForeignKey(
        "blowcomotion.Member",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rental_requests",
    )
    instrument = models.ForeignKey(
        "blowcomotion.Instrument",
        on_delete=models.PROTECT,
        related_name="rental_requests",
    )
    second_choice = models.ForeignKey(
        "blowcomotion.Instrument",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="rental_requests_second_choice",
    )
    third_choice = models.ForeignKey(
        "blowcomotion.Instrument",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="rental_requests_third_choice",
    )
    is_waitlist = models.BooleanField(default=False)
    phone = models.CharField(max_length=255, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    policy_acknowledged = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    patreon_validated = models.BooleanField(
        null=True,
        blank=True,
        help_text="Set automatically via Patreon API at submission time. Active = confirmed; Inactive = not found or inactive; Unknown = API not configured or check failed.",
    )
    patreon_pledge_cents = models.PositiveIntegerField(null=True, blank=True, help_text="Monthly pledge amount in cents at time of last Patreon check.")
    patreon_last_charge_date = models.DateTimeField(null=True, blank=True, help_text="Date of last Patreon charge attempt.")
    patreon_last_charge_status = models.CharField(max_length=20, null=True, blank=True, help_text="Last Patreon charge status at time of check (e.g. Paid, Declined).")
    patreon_patron_since = models.DateTimeField(null=True, blank=True, help_text="Date the member started their Patreon pledge.")
    patreon_lifetime_cents = models.PositiveIntegerField(null=True, blank=True, help_text="Lifetime Patreon support in cents at time of last check.")
    admin_message = models.TextField(blank=True)
    assigned_unit = models.ForeignKey(
        "blowcomotion.LibraryInstrument",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rental_assignments",
    )
    prior_storage_location = models.ForeignKey(
        "blowcomotion.InstrumentStorageLocation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Storage location the instrument was in before being rented out. Restored on return.",
    )

    def __str__(self):
        return f"{self.name} — {self.instrument} ({self.status}) on {self.date_submitted:%Y-%m-%d}"

    class Meta:
        ordering = ["-date_submitted"]
        verbose_name = "Instrument Rental Request"
        verbose_name_plural = "Instrument Rental Requests"
