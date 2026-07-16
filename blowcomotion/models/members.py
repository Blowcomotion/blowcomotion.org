import datetime
import uuid as uuid_module

from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.forms import WagtailAdminModelForm
from wagtail.models import Orderable, RevisionMixin
from wagtail.search import index

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models

from members.utils import generate_unique_username, validate_birthday


class MemberInstrument(Orderable):
    member = ParentalKey("blowcomotion.Member", related_name="additional_instruments")
    instrument = models.ForeignKey("blowcomotion.Instrument", on_delete=models.CASCADE)

    panels = [
        "instrument",
    ]


class Member(RevisionMixin, ClusterableModel, index.Indexed):
    """
    Model for members of the organization

    Name and email live on the linked auth User (single source of truth);
    ``first_name``, ``last_name`` and ``email`` are exposed as write-through
    properties that delegate to ``self.user``. Values assigned before a User
    exists are buffered and materialized into a new User on save().

    Attributes:
        preferred_name: CharField
        primary_instrument: ForeignKey - primary instrument (single choice)
        additional_instruments: ManyToManyField - additional instruments through MemberInstrument
        birth_month: IntegerField
        birth_day: IntegerField
        birth_year: IntegerField
        join_date: DateField
        is_active: BooleanField
        bio: TextField
        image: ForeignKey
        instructor: BooleanField
        board_member: BooleanField
        renting: BooleanField
        last_seen: DateField
        separation_date: DateField
        gigomatic_username: CharField
        gigomatic_id: IntegerField
        phone: CharField
        address: CharField
        city: CharField
        state: CharField
        zip_code: CharField
        country: CharField
        notes: TextField
        emergency_contact: TextField
    """

    preferred_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Name the member prefers to be called (optional)"
    )
    primary_instrument = models.ForeignKey(
        "blowcomotion.Instrument",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="primary_members",
        help_text="Primary instrument played by this member"
    )
    birth_month = models.IntegerField(
        blank=True,
        null=True,
        choices=[
            (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
            (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
            (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
        ],
        help_text="Birth month (1-12)"
    )
    birth_day = models.IntegerField(
        blank=True,
        null=True,
        help_text="Birth day (1-31)"
    )
    birth_year = models.IntegerField(
        blank=True,
        null=True,
        help_text="Birth year (YYYY)"
    )
    join_date = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    bio = models.TextField(blank=True, null=True)
    image = models.ForeignKey(
        "blowcomotion.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    instructor = models.BooleanField(default=False)
    board_member = models.BooleanField(default=False)
    renting = models.BooleanField(
        default=False,
        help_text="Is the member renting an instrument? (Auto-updated when instruments are rented/returned)"
    )
    last_seen = models.DateField(blank=True, null=True, help_text="This field auto-populates whenever attendance is taken.")
    separation_date = models.DateField(blank=True, null=True, help_text="Date of separation from the organization.")
    reactivated_date = models.DateField(blank=True, null=True, help_text="Date when the member was reactivated (is_active changed to True).")
    gigomatic_username = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Username used on Gig-O-Matic for this member",
    )
    gigomatic_id = models.IntegerField(
        blank=True,
        null=True,
        help_text="ID used on Gig-O-Matic for this member",
    )
    phone = models.CharField(max_length=255, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    state = models.CharField(max_length=255, blank=True, null=True)
    zip_code = models.CharField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    emergency_contact = models.TextField(
        blank=True,
        null=True,
        help_text="Name and phone number of emergency contact",
    )
    inspired_by = models.TextField(
        blank=True,
        null=True,
        help_text="What event or person inspired this member to join the band",
    )

    # Shirt size
    SHIRT_SIZE_CHOICES = [
        ('S', 'S'),
        ('M', 'M'),
        ('L', 'L'),
        ('XL', 'XL'),
        ('2XL', '2XL'),
        ('3XL', '3XL'),
        ('4XL', '4XL'),
    ]
    shirt_size = models.CharField(
        max_length=10,
        blank=True,
        choices=SHIRT_SIZE_CHOICES,
        help_text="Adult unisex shirt size",
    )

    # Dietary preferences (multi-select stored as JSON list)
    dietary_preferences = models.JSONField(
        blank=True,
        default=list,
        help_text="List of dietary preferences/practices",
    )
    dietary_other = models.TextField(
        blank=True,
        help_text="Other dietary preference details",
    )

    # Allergy information
    has_allergies = models.BooleanField(
        null=True,
        blank=True,
        help_text="Does the member have food/substance allergies?",
    )
    allergens = models.JSONField(
        blank=True,
        default=list,
        help_text="List of allergens the member has",
    )
    allergens_other = models.TextField(
        blank=True,
        help_text="Other allergen details",
    )
    has_epipen = models.BooleanField(
        null=True,
        blank=True,
        help_text="Does the member carry an Epi-Pen or other intervention?",
    )
    allergy_details = models.TextField(
        blank=True,
        help_text="Additional details about allergies or interventions",
    )

    # Confidential medical notes
    medical_notes = models.TextField(
        blank=True,
        help_text="CONFIDENTIAL: Any medical concerns or allergies (not shared outside admin)",
    )

    # Auth
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="member",
    )
    pending_email = models.EmailField(null=True, blank=True)
    invite_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the set-password invite email was last sent by invite_members",
    )

    # Notification preferences
    notify_rental_updates = models.BooleanField(default=True)
    notify_reminders = models.BooleanField(default=True)
    notify_announcements = models.BooleanField(default=True)

    # Patreon cache — populated by validate_patreon_rentals / admin refresh
    patreon_is_active = models.BooleanField(null=True, blank=True)
    patreon_pledge_cents = models.PositiveIntegerField(null=True, blank=True)
    patreon_last_charge_date = models.DateTimeField(null=True, blank=True)
    patreon_last_charge_status = models.CharField(max_length=20, null=True, blank=True)
    patreon_patron_since = models.DateTimeField(null=True, blank=True)
    patreon_lifetime_cents = models.PositiveIntegerField(null=True, blank=True)
    patreon_last_synced = models.DateTimeField(null=True, blank=True)

    # Commenting out search_fields to avoid FTS indexing issues
    # Admin search still works via snippet_viewsets.py search_fields
    search_fields = [
        index.RelatedFields("user", [
            index.SearchField("first_name"),
            index.SearchField("last_name"),
            index.SearchField("email"),
            index.AutocompleteField("first_name"),
            index.AutocompleteField("last_name"),
        ]),
        index.SearchField("preferred_name"),
        index.SearchField("gigomatic_username"),
        index.AutocompleteField("preferred_name"),
        index.AutocompleteField("gigomatic_username"),
        index.SearchField("bio"),
        index.SearchField("phone"),
        index.SearchField("address"),
        index.SearchField("city"),
        index.SearchField("state"),
        index.SearchField("zip_code"),
        index.SearchField("country"),
        index.SearchField("notes"),
    ]

    # ── Name/email delegation to the linked User ──────────────────────────────
    # The auth User is the single source of truth for first_name, last_name
    # and email. Assignments made before a User exists are buffered in
    # _pending_user_data and materialized into a User by save().

    @property
    def _pending_user_fields(self):
        return self.__dict__.setdefault("_pending_user_data", {})

    @property
    def first_name(self):
        if self.user is not None:
            return self.user.first_name
        return self._pending_user_fields.get("first_name", "")

    @first_name.setter
    def first_name(self, value):
        value = value or ""
        if self.user is not None:
            if self.user.first_name != value:
                self.user.first_name = value
                self._user_sync_needed = True
        else:
            self._pending_user_fields["first_name"] = value

    @property
    def last_name(self):
        if self.user is not None:
            return self.user.last_name
        return self._pending_user_fields.get("last_name", "")

    @last_name.setter
    def last_name(self, value):
        value = value or ""
        if self.user is not None:
            if self.user.last_name != value:
                self.user.last_name = value
                self._user_sync_needed = True
        else:
            self._pending_user_fields["last_name"] = value

    @property
    def email(self):
        if self.user is not None:
            return self.user.email
        return self._pending_user_fields.get("email", "")

    @email.setter
    def email(self, value):
        value = (value or "").strip()
        if self.user is not None:
            if self.user.email != value:
                self.user.email = value
                self._user_sync_needed = True
        else:
            self._pending_user_fields["email"] = value

    def _sync_user_fields(self):
        """Persist buffered/dirty name and email values onto the linked User.

        Called from save(). Creates a User when the member has none yet but
        has buffered values; keeps User.username aligned with the email
        address (the login identifier) when it can do so without colliding
        with another account.

        Security: a member with no linked User NEVER adopts a pre-existing
        auth User, even one whose username matches the member's email. That
        account could belong to unrelated (e.g. staff) auth-only users with
        no Member row, and adopting it would let a public signup rename/take
        over someone else's account. Linking a member to an already-existing
        account is only ever done by the invite/set-password flow
        (members.auth.create_member_user) or the one-time migration.
        """
        UserModel = get_user_model()
        pending = self.__dict__.pop("_pending_user_data", None)

        if not self.user_id:
            if not pending or not any(pending.values()):
                return
            email = (pending.get("email") or "").strip()
            first_name = pending.get("first_name", "")
            last_name = pending.get("last_name", "")

            user = UserModel(
                username=generate_unique_username(email, first_name, last_name),
                email=email,
            )
            user.set_unusable_password()
            if first_name:
                user.first_name = first_name
            if last_name:
                user.last_name = last_name
            user.save()
            self.user = user
            return

        if not pending and not getattr(self, "_user_sync_needed", False):
            return

        user = self.user
        if pending:
            # Values assigned before the user was linked; apply them now.
            for field in ("first_name", "last_name", "email"):
                value = pending.get(field)
                if value and getattr(user, field) != value:
                    setattr(user, field, value)
                    self._user_sync_needed = True

        if getattr(self, "_user_sync_needed", False):
            # Truncate consistently with generate_unique_username: auth_user
            # .username is varchar(150); leave room and check the collision
            # against the value that will actually be assigned.
            desired_username = (user.email or "").strip()[:140]
            if desired_username and user.username != desired_username:
                collision = (
                    UserModel.objects.exclude(pk=user.pk)
                    .filter(username__iexact=desired_username)
                    .exists()
                )
                if not collision:
                    user.username = desired_username
            if user.pk:
                user.save(update_fields=["first_name", "last_name", "email", "username"])
            else:
                user.save()
            self._user_sync_needed = False

    def clean(self):
        from django.core.exceptions import ValidationError

        # Check for duplicate members based on first and last name
        if self.first_name and self.last_name:
            existing_members = Member.objects.filter(
                user__first_name__iexact=self.first_name,
                user__last_name__iexact=self.last_name
            )

            # If this is an update (not a new member), exclude the current instance
            if self.pk:
                existing_members = existing_members.exclude(pk=self.pk)

            if existing_members.exists():
                raise ValidationError(
                    f"A member with the name '{self.first_name} {self.last_name}' already exists. "
                    "Please check if this person is already in the system or use a different name."
                )

        # Existing birthday validation
        validate_birthday(self.birth_day, self.birth_month)

    @property
    def birthday(self):
        """Return birthday as a date object if year is available, otherwise None"""
        if self.birth_year and self.birth_month and self.birth_day:
            import datetime
            try:
                return datetime.date(self.birth_year, self.birth_month, self.birth_day)
            except ValueError:
                return None
        return None

    @property
    def birthday_display(self):
        """Return a formatted birthday string for display"""
        if self.birth_month and self.birth_day:
            month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                         'July', 'August', 'September', 'October', 'November', 'December']
            month_name = month_names[self.birth_month - 1]
            if self.birth_year:
                return f"{month_name} {self.birth_day}, {self.birth_year}"
            else:
                return f"{month_name} {self.birth_day}"
        return None

    @property
    def full_name(self):
        """Return the preferred full name for display."""
        if self.preferred_name:
            return f"{self.preferred_name} {self.last_name}"
        return f"{self.first_name} {self.last_name}"

    def get_gigo_id(self):
        """
        Get the Gig-O-Matic member ID for this member.
        If gigomatic_id is not set, query the GO3 API by email to fetch it.
        Returns the member ID or None if not found.
        """
        # Return cached value if already set
        if self.gigomatic_id:
            return self.gigomatic_id

        # Check if we have an email to query with
        if not self.email:
            return None

        # Import here to avoid circular imports
        import logging
        from urllib.parse import quote

        from django.conf import settings

        from gigs.gigo import make_gigo_api_request

        logger = logging.getLogger(__name__)

        # Check if API is configured
        if not settings.GIGO_API_URL or not settings.GIGO_API_KEY:
            logger.warning(f"GO3 API not configured, cannot query member ID for {self.email}")
            return None

        # Query the member by email
        try:
            endpoint = f"/members/query?email={quote(self.email)}"
            response = make_gigo_api_request(endpoint)

            if response and 'member_id' in response:
                # Cache the member ID
                self.gigomatic_id = response['member_id']
                self.save(update_fields=['gigomatic_id'], sync_go3=False)
                logger.info(f"Fetched and cached GO3 member ID {self.gigomatic_id} for {self.email}")
                return self.gigomatic_id
            else:
                logger.warning(f"Could not find GO3 member ID for {self.email}")
                return None
        except Exception as e:
            logger.error(f"Error querying GO3 API for member {self.email}: {e}")
            return None

    def save(self, *args, **kwargs):
        """
        Override save to sync is_active status with Gig-O-Matic's is_occasional field.
        When is_active changes:
        - False (inactive) → occasional=True in GO3
        - True (active) → occasional=False in GO3
        
        Args:
            sync_go3 (bool): Whether to sync with GO3 API. Set to False for internal
                            updates that don't need GO3 synchronization (default: True)
        
        Performance Note:
            GO3 member verification is only performed when needed:
            - When email changes
            - When is_active changes
            - When gigomatic_id or gigomatic_username are missing
            This avoids unnecessary API calls on high-frequency updates like attendance.
        """
        import logging
        from urllib.parse import quote

        from django.conf import settings

        from gigs.gigo import make_gigo_api_request

        logger = logging.getLogger(__name__)

        # Extract sync_go3 kwarg (defaults to True for backward compatibility)
        sync_go3 = kwargs.pop('sync_go3', True)

        # Extract update_fields to check if specific fields are being updated
        update_fields = kwargs.get('update_fields')

        # Determine if this save operation can affect fields relevant for GO3 sync.
        # Email changes flow through the linked User; they reach this method via
        # full saves (update_fields=None), e.g. the Wagtail admin form.
        sync_relevant_fields = (
            update_fields is None
            or 'is_active' in update_fields
        )

        # Track changes that require GO3 sync
        is_active_changed = False
        email_changed = False
        old_is_active = None
        old_email = None

        # Check if GO3 is configured to short-circuit unnecessary work
        is_go3_configured = (settings.GIGO_API_URL and settings.GIGO_API_KEY)

        # Only fetch the old instance when GO3 sync is enabled, configured, and relevant fields may change
        if self.pk and sync_go3 and is_go3_configured and sync_relevant_fields:
            try:
                old_instance = Member.objects.get(pk=self.pk)
                old_is_active = old_instance.is_active
                old_email = old_instance.email

                # Values are considered changed only when they actually differ
                if old_is_active != self.is_active:
                    is_active_changed = True
                if old_email != self.email:
                    email_changed = True
            except Member.DoesNotExist:
                pass
        else:
            # Even if sync_go3=False, check for reactivation to set reactivated_date
            # Only fetch if is_active could be changing (avoid needless DB query)
            if self.pk and (update_fields is None or 'is_active' in update_fields):
                try:
                    old_instance = Member.objects.get(pk=self.pk)
                    old_is_active = old_instance.is_active
                    if old_is_active != self.is_active:
                        is_active_changed = True
                except Member.DoesNotExist:
                    pass

        # Set reactivated_date if transitioning from inactive to active
        reactivated_date_set = False
        if is_active_changed and old_is_active is not None and not old_is_active and self.is_active:
            self.reactivated_date = datetime.date.today()
            reactivated_date_set = True

        # Ensure reactivated_date is persisted when using update_fields
        if reactivated_date_set and 'update_fields' in kwargs and kwargs['update_fields'] is not None:
            update_fields = kwargs['update_fields']
            if isinstance(update_fields, (list, tuple, set)):
                update_fields = set(update_fields)
            else:
                update_fields = {update_fields}
            update_fields.add('reactivated_date')
            kwargs['update_fields'] = update_fields

        # Persist name/email changes (and create a User for brand-new members)
        # before saving the member row, so self.user_id is set for the insert.
        had_user = bool(self.user_id)
        self._sync_user_fields()
        if not had_user and self.user_id and kwargs.get('update_fields') is not None:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'user'}

        # Call parent save
        super().save(*args, **kwargs)

        # Only query GO3 when sync_go3=True AND sync_relevant_fields=True AND one of these conditions is met:
        # 1. gigomatic_id or gigomatic_username is missing
        # 2. Email changed
        # 3. is_active changed
        # This prevents unrelated field updates (e.g., update_fields=['renting']) from triggering API calls
        should_verify_member = (
            sync_go3 and
            self.email and
            is_go3_configured and
            sync_relevant_fields and
            (not self.gigomatic_id or not self.gigomatic_username or email_changed or is_active_changed)
        )

        if should_verify_member:
            try:
                endpoint = f"/members/query?email={quote(self.email)}"
                member_data = make_gigo_api_request(endpoint)

                if member_data and 'member_id' in member_data:
                    # Track what needs updating
                    update_fields = []

                    # Update gigo_id if different or not set
                    if self.gigomatic_id != member_data['member_id']:
                        logger.info(f"Updating gigo_id for {self.full_name}: {self.gigomatic_id} → {member_data['member_id']}")
                        self.gigomatic_id = member_data['member_id']
                        update_fields.append('gigomatic_id')

                    # Update username if different or not set
                    if member_data.get('username') and self.gigomatic_username != member_data['username']:
                        logger.info(f"Updating gigomatic_username for {self.full_name}: {self.gigomatic_username} → {member_data['username']}")
                        self.gigomatic_username = member_data['username']
                        update_fields.append('gigomatic_username')

                    # Save updated fields if they changed
                    if update_fields:
                        # When using update_fields, we cannot use force_insert/force_update
                        extra_save_kwargs = {
                            key: value
                            for key, value in kwargs.items()
                            if key in ("using",)
                        }
                        extra_save_kwargs["update_fields"] = update_fields
                        super().save(**extra_save_kwargs)
                else:
                    logger.warning(f"Could not verify member info from GO3 for {self.email}")
            except Exception as e:
                logger.warning(f"Error verifying member info from GO3: {e}")

        # If is_active changed, sync status with GO3
        if is_active_changed and sync_go3:
            # Check if API is configured before attempting status sync
            if not is_go3_configured:
                logger.debug(f"GO3 API not configured, skipping status sync for {self.full_name}")
                return

            try:
                # Get gigo_id (should be updated from verification above)
                gigo_id = self.gigomatic_id or self.get_gigo_id()
                if gigo_id:
                    # Determine which band ID to use
                    if settings.DEBUG:
                        band_id = getattr(settings, 'GIGO_BAND_ID_LOCAL', None)
                    else:
                        band_id = getattr(settings, 'GIGO_BAND_ID', None)

                    if band_id:
                        # Determine desired occasional status based on is_active
                        # inactive member (is_active=False) should be occasional (is_occasional=True)
                        # active member (is_active=True) should be regular (is_occasional=False)
                        desired_occasional = not self.is_active

                        # Toggle member status in GO3
                        endpoint = f"/bands/{band_id}/members/{gigo_id}/occasional"
                        response = make_gigo_api_request(endpoint, method='PATCH')

                        if response and 'is_occasional' in response:
                            # Check if the result matches what we want
                            if response['is_occasional'] == desired_occasional:
                                # Success
                                status = "occasional" if desired_occasional else "regular"
                                logger.info(f"Synced member {self.full_name} to {status} in GO3")
                            else:
                                # Toggle didn't result in desired state, toggle again
                                response2 = make_gigo_api_request(endpoint, method='PATCH')
                                if response2 and response2.get('is_occasional') == desired_occasional:
                                    status = "occasional" if desired_occasional else "regular"
                                    logger.info(f"Synced member {self.full_name} to {status} in GO3 (after second toggle)")
                                else:
                                    logger.warning(f"Could not sync member {self.full_name} status to GO3")
                        else:
                            logger.warning(f"Could not sync member {self.full_name} status to GO3 - invalid response")
                    else:
                        logger.debug(f"GIGO_BAND_ID not configured, skipping GO3 sync for {self.full_name}")
                else:
                    logger.debug(f"No Gig-O-Matic ID found for member {self.full_name}, skipping GO3 sync")
            except Exception as e:
                # Log error but don't fail the save
                logger.error(f"Error syncing member {self.full_name} status to GO3: {e}")

    def __str__(self):
        return f"\"{self.preferred_name}\" {self.first_name} {self.last_name}" if self.preferred_name and self.preferred_name.strip().lower() != self.first_name.strip().lower() else f"{self.first_name} {self.last_name}"

    def display_name(self):
        # ponytail: __str__ unsortable in Wagtail admin (label_for_field returns builtin str as attr); this wrapper exposes admin_order_field
        return str(self)
    display_name.admin_order_field = 'user__first_name'
    display_name.short_description = 'Name'


class MemberAdminForm(WagtailAdminModelForm):
    """Wagtail admin form for Member.

    first_name / last_name / email are not model fields anymore — they live on
    the linked auth User. Declaring them here keeps the existing FieldPanels
    working; values are applied to the instance (write-through properties)
    before model validation so the duplicate-name check in Member.clean() sees
    the submitted values.
    """

    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None and self.instance.pk:
            self.initial.setdefault("first_name", self.instance.first_name)
            self.initial.setdefault("last_name", self.instance.last_name)
            self.initial.setdefault("email", self.instance.email)

    def _post_clean(self):
        for field in ("first_name", "last_name", "email"):
            if field in self.cleaned_data:
                setattr(self.instance, field, self.cleaned_data[field])
        super()._post_clean()


Member.base_form_class = MemberAdminForm


class PasswordSetToken(models.Model):
    member = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name="set_password_tokens"
    )
    uuid = models.UUIDField(default=uuid_module.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)
    superseded = models.BooleanField(default=False)

    def __str__(self):
        return f"PasswordSetToken({self.member}, used={self.used})"


class EmailChangeToken(models.Model):
    member = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name="email_change_tokens"
    )
    uuid = models.UUIDField(default=uuid_module.uuid4, unique=True, editable=False)
    new_email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    def __str__(self):
        return f"EmailChangeToken({self.member} → {self.new_email})"
