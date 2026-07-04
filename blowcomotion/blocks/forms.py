from wagtail import blocks


class ContactFormBlock(blocks.StructBlock):
    title = blocks.CharBlock(
        required=False,
        help_text="Enter the title for the contact form.",
    )
    description = blocks.RichTextBlock(
        required=False,
        help_text="Enter the description for the contact form.",
    )
    button_text = blocks.CharBlock(
        required=False,
        help_text="Enter the text for the button.",
    )
    newsletter_opt_in = blocks.BooleanBlock(
        required=False,
        help_text="Include an opt-in checkbox for the newsletter.",
    )


    class Meta:
        icon = "form"
        template = "blocks/contact_form_block.html"
        label_format = "Contact Form: {title}"
        help_text = "This contact form block displays a form for users to fill out. Submissions are sent to the email address specified in the settings. Submissions are also saved to the admin."


class JoinBandFormBlock(blocks.StructBlock):
    title = blocks.CharBlock(
        required=False,
        help_text="Enter the title for the join band form.",
    )
    description = blocks.RichTextBlock(
        required=False,
        help_text="Enter the description for the join band form.",
    )
    button_text = blocks.CharBlock(
        required=False,
        help_text="Enter the text for the button.",
    )
    instrument_field_label = blocks.CharBlock(
        required=False,
        default="What instrument do you play?",
        help_text="Enter the label for the instrument field.",
    )
    instrument_rental_field_label = blocks.CharBlock(
        required=False,
        default="Would you like to rent an instrument?",
        help_text="Enter the label for the instrument rental field.",
    )
    message_field_label = blocks.CharBlock(
        required=False,
        default="Additional message/notes:",
        help_text="Enter the label for the message field.",
    )
    newsletter_opt_in = blocks.BooleanBlock(
        required=False,
        help_text="Include an opt-in checkbox for the newsletter.",
    )


    class Meta:
        icon = "group"
        template = "blocks/join_band_form_block.html"
        label_format = "Join Band Form: {title}"
        help_text = "This join band form block displays a form for people interested in joining the band. Submissions are sent to the email address specified in the settings. Submissions are also saved to the admin."


class BookingFormBlock(blocks.StructBlock):
    title = blocks.CharBlock(
        required=False,
        help_text="Enter the title for the booking form.",
    )
    description = blocks.RichTextBlock(
        required=False,
        help_text="Enter the description for the booking form.",
    )
    button_text = blocks.CharBlock(
        required=False,
        help_text="Enter the text for the button.",
    )
    name_field_label = blocks.CharBlock(
        required=False,
        default="Your Name:",
        help_text="Enter the label for the name field.",
    )
    email_field_label = blocks.CharBlock(
        required=False,
        default="Your Email:",
        help_text="Enter the label for the email field.",
    )
    event_date_field_label = blocks.CharBlock(
        required=False,
        default="Event Date:",
        help_text="Enter the label for the event date field.",
    )
    event_time_field_label = blocks.CharBlock(
        required=False,
        default="Event Time:",
        help_text="Enter the label for the event time field.",
    )
    event_location_field_label = blocks.CharBlock(
        required=False,
        default="Event Location:",
        help_text="Enter the label for the event location field.",
    )
    duration_field_label = blocks.CharBlock(
        required=False,
        default="How long should the band play:",
        help_text="Enter the label for the duration field.",
    )
    expected_guests_field_label = blocks.CharBlock(
        required=False,
        default="Expected number of guests:",
        help_text="Enter the label for the expected guests field.",
    )
    event_details_field_label = blocks.CharBlock(
        required=False,
        default="Event details and expectations:",
        help_text="Enter the label for the event details field.",
    )
    budget_field_label = blocks.CharBlock(
        required=False,
        default="Budget:",
        help_text="Enter the label for the budget field.",
    )
    message_field_label = blocks.CharBlock(
        required=False,
        default="Additional comments or questions:",
        help_text="Enter the label for the message field.",
    )
    newsletter_opt_in = blocks.BooleanBlock(
        required=False,
        help_text="Include an opt-in checkbox for the newsletter.",
    )


    class Meta:
        icon = "calendar-alt"
        template = "blocks/booking_form_block.html"
        label_format = "Booking Form: {title}"
        help_text = "This booking form block displays a form for people interested in booking the band for events. Submissions are sent to the email address specified in the settings. Submissions are also saved to the admin."


class DonateFormBlock(blocks.StructBlock):
    title = blocks.CharBlock(
        required=False,
        help_text="Enter the title for the donate form.",
    )
    description = blocks.RichTextBlock(
        required=False,
        help_text="Enter the description for the donate form.",
    )
    button_text = blocks.CharBlock(
        required=False,
        help_text="Enter the text for the button.",
    )
    name_field_label = blocks.CharBlock(
        required=False,
        default="Your Name:",
        help_text="Enter the label for the name field.",
    )
    email_field_label = blocks.CharBlock(
        required=False,
        default="Your Email:",
        help_text="Enter the label for the email field.",
    )
    message_field_label = blocks.CharBlock(
        required=False,
        default="Message:",
        help_text="Enter the label for the message field.",
    )
    newsletter_opt_in = blocks.BooleanBlock(
        required=False,
        help_text="Include an opt-in checkbox for the newsletter.",
    )


    class Meta:
        icon = "bi-currency-dollar"
        template = "blocks/donate_form_block.html"
        label_format = "Donate Form: {title}"
        help_text = "This donate form block displays a form for people interested in making donations. Submissions are sent to the email address specified in the settings. Submissions are also saved to the admin."


class MemberSignupFormBlock(blocks.StructBlock):
    title = blocks.CharBlock(
        required=False,
        help_text="Enter the title for the member signup form.",
    )
    description = blocks.RichTextBlock(
        required=False,
        help_text="Enter the description for the member signup form.",
    )
    button_text = blocks.CharBlock(
        required=False,
        default="Submit Application",
        help_text="Enter the text for the button.",
    )
    newsletter_opt_in = blocks.BooleanBlock(
        required=False,
        help_text="Include an opt-in checkbox for the newsletter.",
    )

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context=parent_context)
        # Import here to avoid circular imports
        from blowcomotion.models import Instrument
        from members.forms import MemberSignupForm
        context['instruments'] = Instrument.objects.filter(hide_from_member_forms=False).order_by('name')
        context['shirt_size_choices'] = MemberSignupForm.SHIRT_SIZE_CHOICES
        context['dietary_choices'] = MemberSignupForm.DIETARY_CHOICES
        context['allergen_choices'] = MemberSignupForm.ALLERGEN_CHOICES
        return context

    class Meta:
        icon = "group"
        template = "blocks/member_signup_form_block.html"
        label_format = "Member Signup Form: {title}"
        help_text = "This member signup form block displays a form for new members to sign up. Submissions create Member records and send notification emails."


class PayPalDonateButton(blocks.StructBlock):
    button_alignment = blocks.ChoiceBlock(
        choices=[
            ("left", "Left"),
            ("center", "Center"),
            ("right", "Right"),
        ],
        default="center",
        help_text="Select the alignment for the button.",
    )
    button_width = blocks.ChoiceBlock(
        choices=[
            ("half", "Half"),
            ("full", "Full"),
        ],
        default="half",
        help_text="Select the width for the button.",
    )
    button_text = blocks.CharBlock(
        required=False,
        default="Donate with PayPal",
        help_text="Enter the text for the button.",
    )

    class Meta:
        icon = "bi-paypal"
        template = "blocks/paypal_donate_button.html"
        label = "PayPal Donate Button"
        label_format = "PayPal Donate Button: {button_text}"
        help_text = "This PayPal donate button is used to make Paypal donations. The PayPal url is set in the settings if your admin account has permission to change it. The button will be aligned according to the selected alignment."


class VenmoDonateButton(blocks.StructBlock):
    button_text = blocks.CharBlock(
        required=False,
        help_text="Enter the text for the button.",
    )
    button_alignment = blocks.ChoiceBlock(
        choices=[
            ("left", "Left"),
            ("center", "Center"),
            ("right", "Right"),
        ],
        default="center",
        help_text="Select the alignment for the button.",
    )
    button_width = blocks.ChoiceBlock(
        choices=[
            ("half", "Half"),
            ("full", "Full"),
        ],
        default="half",
        help_text="Select the width for the button.",
    )

    class Meta:
        icon = "bi-currency-dollar"
        template = "blocks/venmo_donate_button.html"
        label = "Venmo Donate Button"
        label_format = "Venmo Donate Button: {button_text}"
        help_text = "This is Venmo donate button adds a button for making Venmo donations. The Venmo url is set in the settings if your admin account has permission to change it. The button will be aligned according to the selected alignment."


class PatreonButton(blocks.StructBlock):
    button_text = blocks.CharBlock(
        required=False,
        help_text="Enter the text for the button.",
    )
    button_alignment = blocks.ChoiceBlock(
        choices=[
            ("left", "Left"),
            ("center", "Center"),
            ("right", "Right"),
        ],
        default="center",
        help_text="Select the alignment for the button.",
    )
    button_width = blocks.ChoiceBlock(
        choices=[
            ("half", "Half"),
            ("full", "Full"),
        ],
        default="half",
        help_text="Select the width for the button.",
    )

    class Meta:
        icon = "bi-currency-dollar"
        template = "blocks/patreon_button.html"
        label = "Patreon Button"
        label_format = "Patreon Button: {button_text}"
        help_text = "This is Patreon button adds a button for making Patreon donations. The Patreon url is set in the settings if your admin account has permission to change it. The button will be aligned according to the selected alignment."


class SquareDonateButton(blocks.StructBlock):
    button_text = blocks.CharBlock(
        required=False,
        help_text="Enter the text for the button.",
    )
    button_alignment = blocks.ChoiceBlock(
        choices=[
            ("left", "Left"),
            ("center", "Center"),
            ("right", "Right"),
        ],
        default="center",
        help_text="Select the alignment for the button.",
    )
    button_width = blocks.ChoiceBlock(
        choices=[
            ("half", "Half"),
            ("full", "Full"),
        ],
        default="half",
        help_text="Select the width for the button.",
    )

    class Meta:
        icon = "bi-currency-dollar"
        template = "blocks/square_donate_button.html"
        label = "Square Donate Button"
        label_format = "Square Donate Button: {button_text}"
        help_text = "This is Square donate button adds a button for making Square donations. The Square url is set in the settings if your admin account has permission to change it. The button will be aligned according to the selected alignment."
