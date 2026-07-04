import os

from wagtail import blocks
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images.blocks import ImageChooserBlock
from wagtailmedia.blocks import VideoChooserBlock

from blowcomotion.chooser_blocks import SongChooserBlock


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
