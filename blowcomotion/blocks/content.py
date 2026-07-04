import datetime
import logging
import uuid

from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock

from django.core.cache import cache

from blowcomotion.chooser_blocks import EventChooserBlock, GigoGigChooserBlock

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
