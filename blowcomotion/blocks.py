import datetime
import logging
import os
import uuid
from datetime import timedelta

from wagtail import blocks
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images.blocks import ImageChooserBlock
from wagtailmedia.blocks import VideoChooserBlock

from django.core.cache import cache

from blowcomotion.chooser_blocks import (
    EventChooserBlock,
    GigoGigChooserBlock,
    SongChooserBlock,
)

logger = logging.getLogger(__name__)

class HeroBlock(blocks.StructBlock):
    image = ImageChooserBlock()
    top_line = blocks.CharBlock(required=False)
    middle_line = blocks.CharBlock(required=False)
    bottom_line = blocks.CharBlock(required=False)
    youtube_url = blocks.URLBlock(required=False)

    class Meta:
        icon = "image"
        template = "blocks/hero_block.html"
        label_format = "Hero: {top_line} {middle_line} {bottom_line}"

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        context['youtube_embed_url'] = ''
        if value.get('youtube_url'):
            youtube_url = value['youtube_url']
            if "watch?v=" in youtube_url:
                video_id = youtube_url.split("watch?v=")[-1].split("&")[0]
            elif "youtu.be/" in youtube_url:
                video_id = youtube_url.split("youtu.be/")[-1].split("?")[0]
            else:
                video_id = ''
            if video_id:
                context['youtube_embed_url'] = f"https://www.youtube.com/embed/{video_id}"
        return context


class EventsBlock(blocks.StructBlock):
    scroller_title = blocks.CharBlock()
    gigo_gigs = blocks.ListBlock(
        blocks.StructBlock(
            [
                ("details", GigoGigChooserBlock()),
                ("event_scroller_image", ImageChooserBlock(required=False)),
            ]
        )
    )
    events = blocks.ListBlock(
        EventChooserBlock(), help_text="Events that are not associated with Gig-o-Matic"
    )

    class Meta:
        icon = "date"
        template = "blocks/events_block.html"
        label_format = "Event Scroller: {scroller_title}"


class AlignableRichtextBlock(blocks.StructBlock):
    rich_text = blocks.RichTextBlock()
    align = blocks.ChoiceBlock(
        choices=[
            ("left", "Left"),
            ("center", "Center"),
            ("right", "Right"),
        ],
        default="left",
    )

    class Meta:
        icon = "edit"
        template = "blocks/alignable_richtext_block.html"
        label_format = "({align}-aligned) {rich_text}"


class HorizontalRuleBlock(blocks.StaticBlock):
    class Meta:
        template = "blocks/horizontal_rule_block.html"
        icon = "minus"
        label = "Horizontal Rule"
        help_text = "This is a horizontal rule block, it adds a horizontal line."
        help_text = "This block adds a horizontal rule."


class SpacerBlock(blocks.StaticBlock):
    class Meta:
        icon = "bi-arrows-expand"
        label = "Spacer"
        template = "blocks/spacer_block.html"
        help_text = "This is a spacer block, it adds 50px of vertical space. It does not display anything."


class AdjustableSpacerBlock(blocks.StructBlock):
    height = blocks.IntegerBlock(
        default=20,
        min_value=1,
        help_text="Enter the height of the spacer in pixels.",
    )

    class Meta:
        icon = "bi-arrows-expand"
        label = "Adjustable Spacer"
        template = "blocks/spacer_block.html"
        help_text = "This is a spacer block, it adds a vertical space between blocks. You can set the height of the spacer in pixels."


class AccordionListBlock(blocks.StructBlock):
    title = blocks.CharBlock(required=False)
    content = blocks.ListBlock(
        blocks.StructBlock(
            [
                ("title", blocks.CharBlock(required=False)),
                ("content", blocks.RichTextBlock(required=False)),
            ]
        )
    )


    class Meta:
        icon = "list-ul"
        template = "blocks/accordion_list_block.html"
        label_format = "Accordion List: {title}"
        help_text = "This is an accordion list block, it displays a list of items that can be expanded or collapsed."


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
        from blowcomotion.forms import MemberSignupForm
        from blowcomotion.models import Instrument
        context['instruments'] = Instrument.objects.all().order_by('name')
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


class ButtonBlock(blocks.StructBlock):
    button_text = blocks.CharBlock(
        required=False,
        help_text="Enter the text for the button.",
    )
    button_url = blocks.URLBlock(
        required=False,
        help_text="Enter the URL for the button.",
    )
    button_target = blocks.ChoiceBlock(
        choices=[
            ("_self", "Same Tab"),
            ("_blank", "New Tab"),
        ],
        default="_self",
        help_text="Select the target for the button.",
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
        icon = "link"
        template = "blocks/button_block.html"
        label_format = "Button: {button_text}"


class JukeBoxBlock(blocks.StructBlock):
    foreground_text = blocks.CharBlock(
        required=False,
        help_text="Enter the foreground title text for the jukebox.",
    )
    background_text = blocks.CharBlock(
        required=False,
        help_text="Enter the background title text for the jukebox.",
    )
    jukebox_image = ImageChooserBlock(
        required=False,
        help_text="Select the image for the jukebox.",
    )
    lazy_loading = blocks.BooleanBlock(
        default=True,
        required=False,
        help_text="Enable lazy loading for better performance. Audio files will only load when the user clicks play.",
    )
    preload_first_track = blocks.BooleanBlock(
        default=True,
        required=False,
        help_text="Preload the first track's metadata for immediate playback. Only applies when lazy loading is enabled.",
    )

    tracks = blocks.ListBlock(
        SongChooserBlock(),
        help_text="Select the songs for the jukebox. A song must have a recording for it to show up in the jukebox.",
        min_num=1,
    )

    class Meta:
        icon = "bi-music-note-beamed"
        template = "blocks/jukebox_block.html"
        


class ChartLibraryBlock(blocks.StructBlock):
    """Block for browsing and searching charts with audio playback."""
    
    title = blocks.CharBlock(
        required=False,
        help_text="Optional title displayed above the chart library.",
    )
    description = blocks.RichTextBlock(
        required=False,
        help_text="Optional description text displayed below the title.",
    )
    show_search = blocks.BooleanBlock(
        default=True,
        required=False,
        help_text="Show a search box to filter songs by title.",
    )
    placeholder_text = blocks.CharBlock(
        required=False,
        default="Search for a song...",
        help_text="Placeholder text for the search input.",
    )

    class Meta:
        icon = "bi-file-earmark-music"
        template = "blocks/chart_library_block.html"
        label = "Chart Library"
        label_format = "Chart Library: {title}"
        help_text = "A searchable interface for browsing charts with audio playback. Songs without charts are automatically filtered out."


class QuoteBlock(blocks.StructBlock):
    quote_text = blocks.RichTextBlock()
    author = blocks.CharBlock(
        required=False,
        help_text="Enter the author of the quote."
    )

    class Meta:
        icon = "openquote"
        template = "blocks/quote_block.html"
        label = "Quote Block"
        label_format = "Quote: {author}"
        help_text = "A block for displaying a quote with optional author."


class ImageBlock(blocks.StructBlock):
    image = ImageChooserBlock()
    url = blocks.URLBlock(required=False, help_text="Optional: Link the image to a URL (e.g. merch page)")

    class Meta:
        icon = "image"
        template = "blocks/image_block.html"
        label_format = "Image: {image}"


class CarouselImageBlock(blocks.StructBlock):
    """Individual image item for carousel with optional caption and link."""
    image = ImageChooserBlock(
        help_text="Select an image for the carousel."
    )
    caption = blocks.CharBlock(
        required=False,
        max_length=200,
        help_text="Optional: Add a caption for this image."
    )
    url = blocks.URLBlock(
        required=False,
        help_text="Optional: Link the image to a URL (e.g., event page, merch)."
    )
    open_in_new_tab = blocks.BooleanBlock(
        required=False,
        default=False,
        help_text="Open link in a new browser tab."
    )

    class Meta:
        icon = "image"
        label = "Carousel Image"


class ImageCarouselBlock(blocks.StructBlock):
    """Block for displaying a carousel of images with lightbox functionality."""
    title = blocks.CharBlock(
        required=False,
        help_text="Main title for the image carousel section (e.g., 'Photo Gallery')."
    )
    subtitle = blocks.CharBlock(
        required=False,
        help_text="Subtitle text displayed above the title (e.g., 'Recent Events')."
    )
    images = blocks.ListBlock(
        CarouselImageBlock(),
        min_num=1,
        help_text="Add images to display in the carousel. Click an image to view it full-size."
    )
    autoplay = blocks.BooleanBlock(
        required=False,
        default=False,
        help_text="Automatically advance slides."
    )
    autoplay_speed = blocks.IntegerBlock(
        required=False,
        default=3000,
        min_value=1000,
        help_text="Autoplay speed in milliseconds (e.g., 3000 = 3 seconds)."
    )
    show_dots = blocks.BooleanBlock(
        required=False,
        default=True,
        help_text="Show navigation dots below the carousel."
    )
    slides_to_show = blocks.ChoiceBlock(
        choices=[
            ("2", "2 Slides (Desktop)"),
            ("3", "3 Slides (Desktop)"),
            ("4", "4 Slides (Desktop)"),
        ],
        default="4",
        help_text="Number of slides visible on desktop screens (>992px)."
    )

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        
        # Generate a unique ID for this carousel instance
        carousel_id = f"carousel-{uuid.uuid4().hex[:8]}"
        
        # Process images with Wagtail image renditions
        processed_images = []
        for img_block in value.get('images', []):
            if img_block.get('image'):
                processed_images.append({
                    'image': img_block['image'],
                    'caption': img_block.get('caption', ''),
                    'url': img_block.get('url', ''),
                    'open_in_new_tab': img_block.get('open_in_new_tab', False),
                })
        
        # Calculate responsive column class based on slides_to_show
        slides = int(value.get('slides_to_show', 4))
        col_class = f"col-lg-{12 // slides}"
        
        context.update({
            'carousel_id': carousel_id,
            'processed_images': processed_images,
            'col_class': col_class,
        })
        
        return context

    class Meta:
        icon = "bi-images"
        template = "blocks/image_carousel_block.html"
        label = "Image Carousel"
        label_format = "Image Carousel: {title}"
        help_text = "Display a carousel of images with click-to-expand lightbox functionality."


class VideoItemOverridesBlock(blocks.StructBlock):
    """Collapsed group of optional override fields for video items."""
    title_override = blocks.CharBlock(
        required=False,
        help_text="Optional: Override the video title from the embed."
    )
    thumbnail_override = ImageChooserBlock(
        required=False,
        help_text="Optional: Use a custom thumbnail instead of the video's thumbnail."
    )
    description = blocks.CharBlock(
        required=False,
        max_length=500,
        help_text="Optional: Add a description or caption for this video."
    )

    class Meta:
        form_classname = "collapsed"
        label = "Optional Overrides"


class VideoItemBlock(blocks.StructBlock):
    """Individual video item with either embed URL OR uploaded video file."""
    video = EmbedBlock(
        required=False,
        help_text="Enter a video URL (YouTube, Vimeo, etc.). Use either this OR the video file field below, not both."
    )
    video_file = VideoChooserBlock(
        required=False,
        help_text="Upload a video file. Use either this OR the video URL field above, not both."
    )
    overrides = VideoItemOverridesBlock(
        required=False,
        help_text="Optional: Override video title, thumbnail, or add a description."
    )

    def clean(self, value):
        """Enforce XOR validation: either video OR video_file must be provided, but not both."""
        from wagtail.blocks import StructBlockValidationError

        from django.core.exceptions import ValidationError
        
        result = super().clean(value)
        
        has_video = bool(result.get('video'))
        has_video_file = bool(result.get('video_file'))
        
        # XOR validation: exactly one must be provided
        if has_video and has_video_file:
            raise StructBlockValidationError(block_errors={
                'video': ValidationError("Cannot provide both a video URL and a video file. Choose one."),
                'video_file': ValidationError("Cannot provide both a video URL and a video file. Choose one."),
            })
        elif not has_video and not has_video_file:
            raise StructBlockValidationError(block_errors={
                'video': ValidationError("Either a video URL or a video file must be provided."),
                'video_file': ValidationError("Either a video URL or a video file must be provided."),
            })
        
        return result

    class Meta:
        icon = "media"
        label = "Video"


class VideoFeedBlock(blocks.StructBlock):
    """Block for displaying a grid of embedded videos with optional featured video."""
    title = blocks.CharBlock(
        required=False,
        help_text="Main title for the video section (e.g., 'Latest Videos')."
    )
    subtitle = blocks.CharBlock(
        required=False,
        help_text="Subtitle text displayed above the title (e.g., 'YouTube Feed')."
    )
    videos = blocks.ListBlock(
        VideoItemBlock(),
        help_text="Add videos to display. The first video can be featured (shown large) if enabled below."
    )
    show_featured = blocks.BooleanBlock(
        required=False,
        default=True,
        help_text="Show the first video as a large featured video above the grid."
    )
    grid_columns = blocks.ChoiceBlock(
        choices=[
            ("2", "2 Columns"),
            ("3", "3 Columns"),
            ("4", "4 Columns"),
        ],
        default="4",
        help_text="Number of columns for the video carousel (Note: currently set to 4 in carousel config)."
    )

    def _get_embed_data(self, embed_value):
        """
        Fetch embed data once per video to avoid N+1 queries.
        Returns both the embed URL and metadata from a single embed fetch.
        """
        import re
        
        if not embed_value or not hasattr(embed_value, 'url') or not embed_value.url:
            return None
        
        try:
            from wagtail.embeds import embeds
            embed = embeds.get_embed(embed_value.url)
            
            # Extract iframe src from embed HTML
            embed_url = None
            if hasattr(embed, 'html') and embed.html:
                iframe_match = re.search(r'<iframe[^>]+src="([^"]+)"', embed.html)
                if iframe_match:
                    embed_url = iframe_match.group(1)
            
            # Fallback: construct embed URL from source URL
            if not embed_url:
                url = embed_value.url
                # YouTube
                if "youtube.com/watch?v=" in url:
                    video_id = url.split("watch?v=")[-1].split("&")[0]
                    embed_url = f"https://www.youtube.com/embed/{video_id}"
                elif "youtu.be/" in url:
                    video_id = url.split("youtu.be/")[-1].split("?")[0]
                    embed_url = f"https://www.youtube.com/embed/{video_id}"
                # Vimeo
                elif "vimeo.com/" in url:
                    video_id = url.split("vimeo.com/")[-1].split("?")[0]
                    embed_url = f"https://player.vimeo.com/video/{video_id}"
            
            return {
                'embed_url': embed_url,
                'thumbnail_url': embed.thumbnail_url,
                'title': embed.title,
                'author_name': embed.author_name,
                'provider_name': embed.provider_name,
            }
        except Exception:
            return None

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        
        # Process videos: handle both embeds and uploaded video files
        # Fetch embed data once per video to avoid N+1 queries
        valid_videos = []
        for v in value.get('videos', []):
            video_data = None
            
            # Check if it's an embed URL
            if v.get('video'):
                # Single embed fetch per video returns both URL and metadata
                embed_data = self._get_embed_data(v['video'])
                if embed_data and embed_data.get('embed_url'):
                    # Create a new dict with the video data plus embed_url and embed metadata
                    video_data = {
                        'video': v['video'],
                        'video_file': None,
                        'is_uploaded': False,
                        'overrides': v.get('overrides', {}),
                        'embed_url': embed_data['embed_url'],
                        'thumbnail_url': embed_data.get('thumbnail_url', ''),
                        'title': embed_data.get('title', ''),
                    }
            # Check if it's an uploaded video file
            elif v.get('video_file'):
                video_file = v['video_file']
                # Extract file extension for MIME type (e.g., 'mp4', 'webm', 'ogg')
                file_extension = os.path.splitext(video_file.file.name)[1].lstrip('.').lower()
                # Fallback to 'mp4' if no extension to avoid invalid MIME types
                if not file_extension:
                    file_extension = 'mp4'
                # Create data dict for uploaded video
                video_data = {
                    'video': None,
                    'video_file': video_file,
                    'is_uploaded': True,
                    'file_extension': file_extension,  # e.g., 'mp4', 'webm' (normalized lowercase)
                    'overrides': v.get('overrides', {}),
                    'embed_url': None,
                    'thumbnail_url': video_file.thumbnail.url if video_file.thumbnail else '',
                    'title': v.get('overrides', {}).get('title_override') or video_file.title,
                }
            
            if video_data:
                valid_videos.append(video_data)
        
        # Separate featured video from grid videos
        featured_video = None
        grid_videos = valid_videos
        
        if value.get('show_featured') and valid_videos:
            featured_video = valid_videos[0]
            grid_videos = valid_videos[1:]
        
        # Calculate Bootstrap column class based on grid_columns
        columns = int(value.get('grid_columns', 4))
        col_class = f"col-lg-{12 // columns}"
        
        context.update({
            'featured_video': featured_video,
            'grid_videos': grid_videos,
            'col_class': col_class,
        })
        
        return context

    class Meta:
        icon = "bi-play-circle"
        template = "blocks/video_feed_block.html"
        label = "Video Feed"
        label_format = "Video Feed: {title}"
        help_text = "Display a collection of embedded videos with optional featured video and grid layout."


class ColumnContentBlock(blocks.StreamBlock):
    accordion_list = AccordionListBlock()
    booking_form = BookingFormBlock(group="Forms")
    button = ButtonBlock()
    contact_form = ContactFormBlock(group="Forms")
    donate_form = DonateFormBlock(group="Forms")
    join_band_form = JoinBandFormBlock(group="Forms")
    horizontal_rule = HorizontalRuleBlock()
    image = ImageBlock()
    image_carousel = ImageCarouselBlock()
    rich_text = AlignableRichtextBlock()
    adjustable_spacer = AdjustableSpacerBlock()
    spacer = SpacerBlock()
    paypal_donate_button = PayPalDonateButton()
    venmo_donate_button = VenmoDonateButton()
    square_donate_button = SquareDonateButton()
    patreon_button = PatreonButton()
    video_feed = VideoFeedBlock()

    class Meta:
        template = "blocks/column_content_block.html"


class ThreeColumnBlock(blocks.StructBlock):
    left_column = ColumnContentBlock(required=False)
    middle_column = ColumnContentBlock(required=False)
    right_column = ColumnContentBlock(required=False)
    show_left_border = blocks.BooleanBlock(
        required=False,
        default=False,
        help_text="Show vertical border on the right side of the left column"
    )
    show_right_border = blocks.BooleanBlock(
        required=False,
        default=False,
        help_text="Show vertical border on the right side of the middle column"
    )
    border_width = blocks.IntegerBlock(
        required=False,
        default=3,
        min_value=1,
        help_text="Border width in pixels"
    )
    border_color = blocks.CharBlock(
        required=False,
        default="#5b1a76",
        help_text="Border color (e.g., #5b1a76 or rgb(91, 26, 118))"
    )
    border_style = blocks.ChoiceBlock(
        choices=[
            ("solid", "Solid"),
            ("dashed", "Dashed"),
            ("dotted", "Dotted"),
        ],
        default="solid",
        help_text="Select the border style"
    )

    class Meta:
        template = "blocks/three_column_block.html"
        label_format = "Three Columns"


class TwoColumnBlock(ThreeColumnBlock):
    middle_column = None
    show_left_border = None
    show_right_border = None
    show_vertical_border = blocks.BooleanBlock(
        required=False,
        default=False,
        help_text="Show vertical border between the two columns"
    )
    left_column_width = blocks.ChoiceBlock(choices=[
            ("one-half", "One Half"),
            ("one-third", "One Third"),
            ("two-thirds", "Two Thirds"),
    ], default="one-half")

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        left_column_width = value["left_column_width"]

        width_map = {
            "one-half": ("6", "6"),
            "one-third": ("4", "8"),
            "two-thirds": ("8", "4"),
        }

        if left_column_width in width_map:
            context["left_column_width"], context["right_column_width"] = width_map[left_column_width]
            
        return context

    class Meta:
        template = "blocks/two_column_block.html"
        label_format = "Two Columns"


class FourColumnBlock(blocks.StructBlock):
    left_column = ColumnContentBlock(required=False)
    middle_left_column = ColumnContentBlock(required=False)
    middle_right_column = ColumnContentBlock(required=False)
    right_column = ColumnContentBlock(required=False)
    show_left_border = blocks.BooleanBlock(
        required=False,
        default=False,
        help_text="Show vertical border on the right side of the left column"
    )
    show_middle_border = blocks.BooleanBlock(
        required=False,
        default=False,
        help_text="Show vertical border on the right side of the middle-left column"
    )
    show_right_border = blocks.BooleanBlock(
        required=False,
        default=False,
        help_text="Show vertical border on the right side of the middle-right column"
    )
    border_width = blocks.IntegerBlock(
        required=False,
        default=3,
        min_value=1,
        help_text="Border width in pixels"
    )
    border_color = blocks.CharBlock(
        required=False,
        default="#5b1a76",
        help_text="Border color (e.g., #5b1a76 or rgb(91, 26, 118))"
    )
    border_style = blocks.ChoiceBlock(
        choices=[
            ("solid", "Solid"),
            ("dashed", "Dashed"),
            ("dotted", "Dotted"),
        ],
        default="solid",
        help_text="Select the border style"
    )

    class Meta:
        template = "blocks/four_column_block.html"
        label_format = "Four Columns"


class ColumnLayoutBlock(blocks.StreamBlock):
    spacer = AdjustableSpacerBlock()
    horizontal_rule = HorizontalRuleBlock()
    two_column = TwoColumnBlock()
    three_column = ThreeColumnBlock()
    four_column = FourColumnBlock()


class MenuItemBlock(blocks.StructBlock):
    page = blocks.PageChooserBlock(required=False)
    label = blocks.CharBlock(required=False)

    def clean(self, value):
        from wagtail.blocks.struct_block import StructBlockValidationError

        from django.core.exceptions import ValidationError
        
        cleaned_data = super().clean(value)
        if not cleaned_data.get('page') and not cleaned_data.get('label'):
            raise StructBlockValidationError({
                'page': ValidationError("Menu item must have either a page or a label.")
            })
        return cleaned_data
    


class MenuItem(blocks.StructBlock):
    page = blocks.PageChooserBlock(required=False)
    label = blocks.CharBlock(required=False)
    submenus = blocks.ListBlock(MenuItemBlock, required=False, collapsed=True)

    def clean(self, value):
        from wagtail.blocks.struct_block import StructBlockValidationError

        from django.core.exceptions import ValidationError
        
        cleaned_data = super().clean(value)
        if not cleaned_data.get('page') and not cleaned_data.get('label'):
            raise StructBlockValidationError({
                'page': ValidationError("Menu item must have either a page or a label.")
            })
        return cleaned_data


class UpcomingPublicGigs(blocks.StructBlock):
    headline = blocks.CharBlock(
        required=False,
        help_text="Enter the headline for the upcoming public gigs.",
    )

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        context['gigs'] = []
        context['error'] = None
        
        try:
            context['gigs'] = cache.get('upcoming_public_gigs')
            if context['gigs'] is None:
                # Import here to avoid circular imports
                from blowcomotion.models import CachedGig

                # Get upcoming confirmed gigs from database cache
                cached_gigs = CachedGig.get_upcoming_gigs()
                
                validated_gigs = []
                for gig in cached_gigs:
                    try:
                        # Filter out private, hidden, archived, and trashed gigs using raw_data
                        raw = gig.raw_data or {}
                        if raw.get('is_private', False):
                            continue
                        if raw.get('hide_from_calendar', False):
                            continue
                        if raw.get('is_archived', False):
                            continue
                        if raw.get('is_in_trash', False):
                            continue
                        
                        # Build gig dict for template
                        from django.utils import timezone
                        
                        validated_gigs.append({
                            'id': gig.gig_id,
                            'title': gig.title,
                            'date': gig.date,
                            'set_time': timezone.make_aware(datetime.datetime.combine(gig.date, gig.time)) if gig.date and gig.time else None,
                            'address': gig.address,
                            'gig_status': gig.gig_status,
                            'band': gig.band,
                        })
                    except Exception as e:
                        # Log individual gig errors but continue processing
                        logger.error(f"Error processing gig {gig.gig_id}: {e}")
                        continue

                # Already sorted by date from get_upcoming_gigs()
                context['gigs'] = validated_gigs

                cache.set('upcoming_public_gigs', context['gigs'], 60 * 60) # cache for 1 hour
        except Exception as e:
            logger.error(f"Error in UpcomingPublicGigs block: {e}")
            context['error'] = None  # Don't show errors to end users
            context['gigs'] = []
        
        return context

    class Meta:
        icon = "date"
        label = "Upcoming Public Gigs"
        help_text = "This displays a list of confirmed upcoming public Blowco gigs as a list. (sourced from gig-o-matic)"
        template = "blocks/upcoming_public_gigs.html"
        preview_value = {}


class QuotedImageBlock(blocks.StructBlock):
    image = ImageChooserBlock()
    header = blocks.CharBlock(required=False)
    subheader = blocks.RichTextBlock(required=False)
    author = blocks.CharBlock(required=False)

    class Meta:
        icon = "image"
        label = "Quoted Image"
        template = "blocks/quoted_image_block.html"
        preview_value = {
            "header": "This is a header",
            "subheader": "This is a subheader",
            "author": "This is an author",
        }


class MultiImageBannerBlock(blocks.StructBlock):
    images = blocks.ListBlock(
        ImageChooserBlock(),
        help_text="Select images to display in the banner.",
        min_num=7,
        max_num=7,
    )

    class Meta:
        icon = "image"
        template = "blocks/multi_image_banner_block.html"
        preview_template = "blocks/previews/multi_image_banner_block.html"
        label_format = "Multi Image Banner"


class FullWidthImageBlock(blocks.StructBlock):
    image = ImageChooserBlock()
    url = blocks.URLBlock(required=False, help_text="Optional: Link the image to a URL (e.g. merch page)")

    class Meta:
        icon = "image"
        template = "blocks/full_width_image_block.html"
        label_format = "Full Width Image: {image}"


class CountdownBlock(blocks.StructBlock):
    background_image = ImageChooserBlock(required=False)
    countdown_date = blocks.DateBlock(
        help_text="Enter the date for the countdown."
    )
    head_line = blocks.CharBlock(
        required=False,
        help_text="Enter the top line text for the countdown.",
    )
    sub_line = blocks.CharBlock(
        required=False,
        help_text="Enter the sub line text for the countdown.",
    )
    button_text = blocks.CharBlock(
        required=False,
        help_text="Enter the text for the button.",
    )
    button_url = blocks.URLBlock(
        required=False,
        help_text="Enter the URL for the button.",
    )
    button_target = blocks.ChoiceBlock(
        choices=[
            ("_self", "Same Tab"),
            ("_blank", "New Tab"),
        ],
        default="_self",
        help_text="Select the target for the button.",
    )

    
    class Meta:
        icon = "calendar-alt"
        template = "blocks/countdown_block.html"
        label_format = "Countdown to {countdown_date}"

    
class TimelineItemBlock(blocks.StructBlock):
    image = ImageChooserBlock(
        required=False,
        help_text="Select an image for this timeline item."
    )
    title = blocks.CharBlock(
        required=False,
        help_text="Enter the title for this timeline item."
    )
    date = blocks.CharBlock(
        required=False,
        help_text="Enter the date or year for this timeline item (e.g. '2017' or 'March 2020')."
    )
    description = blocks.RichTextBlock(
        required=False,
        help_text="Enter the description for this timeline item."
    )

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        
        description = value["description"]
        if description:
            text = str(description)
            has_longtext = len(text) > 310
            p_count = text.lower().count("<p")
            
            context["has_longtext"] = has_longtext
            context["line_count"] = p_count
        else:
            context["has_longtext"] = False
            context["line_count"] = 0
        
        return context

    class Meta:
        icon = "date"
        template = "blocks/timeline_item_block.html"
        label_format = "{title} - {date}"

class TimelineBlock(blocks.StructBlock):
    background_color = blocks.CharBlock(
        required=False,
        default="#F0F2F5",
        help_text="Enter the background color for the timeline section (e.g. #F0F2F5 or rgb(240, 242, 245))."
    )
    timeline_items = blocks.ListBlock(
        TimelineItemBlock(),
        help_text="Add timeline items. They will alternate between left and right automatically.",
        min_num=1,
    )

    class Meta:
        icon = "list-ol"
        template = "blocks/timeline_block.html"
        label = "Timeline"
        help_text = "This displays a timeline with alternating left/right items."

