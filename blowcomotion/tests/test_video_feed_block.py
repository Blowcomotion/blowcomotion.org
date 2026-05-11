"""
Tests for VideoFeedBlock and related blocks.
"""

from unittest.mock import Mock, PropertyMock, patch

from wagtail.embeds.embeds import get_embed
from wagtail.embeds.exceptions import EmbedException

from django.test import TestCase

from blowcomotion.blocks import VideoFeedBlock, VideoItemBlock, VideoItemOverridesBlock


class VideoItemOverridesBlockTests(TestCase):
    """Test cases for VideoItemOverridesBlock"""

    def test_has_expected_fields(self):
        """Test that VideoItemOverridesBlock has all expected fields"""
        block = VideoItemOverridesBlock()
        
        self.assertIn('title_override', block.child_blocks)
        self.assertIn('thumbnail_override', block.child_blocks)
        self.assertIn('description', block.child_blocks)

    def test_is_collapsed_by_default(self):
        """Test that the block has collapsed class in form"""
        block = VideoItemOverridesBlock()
        
        # Check that form_classname includes 'collapsed'
        self.assertEqual(block.meta.form_classname, 'collapsed')

    def test_all_fields_are_optional(self):
        """Test that all override fields are optional"""
        block = VideoItemOverridesBlock()
        
        # Should not raise validation errors with empty values
        value = block.to_python({})
        self.assertIsNotNone(value)


class VideoItemBlockTests(TestCase):
    """Test cases for VideoItemBlock"""

    def test_has_expected_fields(self):
        """Test that VideoItemBlock has video and overrides fields"""
        block = VideoItemBlock()
        
        self.assertIn('video', block.child_blocks)
        self.assertIn('overrides', block.child_blocks)

    def test_video_field_is_embed_block(self):
        """Test that video field is an EmbedBlock"""
        block = VideoItemBlock()
        
        from wagtail.embeds.blocks import EmbedBlock
        self.assertIsInstance(block.child_blocks['video'], EmbedBlock)

    def test_overrides_field_is_video_item_overrides_block(self):
        """Test that overrides field is VideoItemOverridesBlock"""
        block = VideoItemBlock()
        
        self.assertIsInstance(
            block.child_blocks['overrides'], 
            VideoItemOverridesBlock
        )


class VideoFeedBlockTests(TestCase):
    """Test cases for VideoFeedBlock"""

    def test_has_expected_fields(self):
        """Test that VideoFeedBlock has all expected fields"""
        block = VideoFeedBlock()
        
        self.assertIn('title', block.child_blocks)
        self.assertIn('subtitle', block.child_blocks)
        self.assertIn('videos', block.child_blocks)
        self.assertIn('show_featured', block.child_blocks)
        self.assertIn('grid_columns', block.child_blocks)

    def test_videos_field_is_list_block(self):
        """Test that videos field is a ListBlock"""
        block = VideoFeedBlock()
        
        from wagtail.blocks import ListBlock
        self.assertIsInstance(block.child_blocks['videos'], ListBlock)

    def test_grid_columns_default_is_4(self):
        """Test that grid_columns defaults to 4"""
        block = VideoFeedBlock()
        
        grid_columns_block = block.child_blocks['grid_columns']
        self.assertEqual(grid_columns_block.meta.default, '4')

    def test_show_featured_default_is_true(self):
        """Test that show_featured defaults to True"""
        block = VideoFeedBlock()
        
        show_featured_block = block.child_blocks['show_featured']
        self.assertEqual(show_featured_block.meta.default, True)


class VideoFeedBlockContextTests(TestCase):
    """Test cases for VideoFeedBlock.get_context() method"""

    def _create_mock_embed(self, url='https://www.youtube.com/watch?v=test', title='Test Video'):
        """Helper to create a mock embed value that will work with _get_embed_data()"""
        # Create the EmbedValue that gets passed to _get_embed_data
        mock_embed_value = Mock()
        mock_embed_value.url = url
        
        # Create the Embed object that embeds.get_embed() will return
        mock_embed = Mock()
        mock_embed.url = url
        mock_embed.title = title
        mock_embed.thumbnail_url = 'https://example.com/thumb.jpg'
        mock_embed.html = '<iframe src="https://www.youtube.com/embed/test" frameborder="0"></iframe>'
        
        return mock_embed_value, mock_embed

    @patch('wagtail.embeds.embeds.get_embed')
    def test_filters_out_videos_without_embed(self, mock_get_embed):
        """Test that videos without valid embed are filtered out"""
        block = VideoFeedBlock()
        
        # Create two valid embeds
        embed1_value, embed1 = self._create_mock_embed()
        embed2_value, embed2 = self._create_mock_embed(url='https://vimeo.com/123')
        embed2.html = '<iframe src="https://player.vimeo.com/video/123" frameborder="0"></iframe>'
        
        # Setup mock to return different embeds based on URL
        def get_embed_side_effect(url):
            if 'youtube' in url:
                return embed1
            elif 'vimeo' in url:
                return embed2
            return None
        
        mock_get_embed.side_effect = get_embed_side_effect
        
        value = {
            'title': 'My Videos',
            'videos': [
                {'video': embed1_value, 'overrides': {}},
                {'video': None, 'overrides': {}},  # Invalid - should be filtered
                {'video': embed2_value, 'overrides': {}},
            ],
            'show_featured': False,
            'grid_columns': '3',
        }
        
        context = block.get_context(value)
        
        # Should only have 2 valid videos in grid_videos
        self.assertEqual(len(context['grid_videos']), 2)
        self.assertIsNone(context['featured_video'])
        # Check that embed_url was added
        self.assertIn('embed_url', context['grid_videos'][0])

    @patch('wagtail.embeds.embeds.get_embed')
    def test_separates_featured_video_when_enabled(self, mock_get_embed):
        """Test that first video becomes featured when show_featured is True"""
        block = VideoFeedBlock()
        
        # Create mock embeds
        first_value, first_embed = self._create_mock_embed(title='Featured')
        second_value, second_embed = self._create_mock_embed(title='Grid 1')
        third_value, third_embed = self._create_mock_embed(title='Grid 2')
        
        # Mock get_embed to return appropriate embeds
        mock_get_embed.side_effect = [first_embed, second_embed, third_embed]
        
        first_video = {'video': first_value, 'overrides': {}}
        second_video = {'video': second_value, 'overrides': {}}
        third_video = {'video': third_value, 'overrides': {}}
        
        value = {
            'title': 'My Videos',
            'videos': [first_video, second_video, third_video],
            'show_featured': True,
            'grid_columns': '4',
        }
        
        context = block.get_context(value)
        
        # First video should be featured
        self.assertIsNotNone(context['featured_video'])
        self.assertIn('embed_url', context['featured_video'])
        self.assertEqual(context['featured_video']['title'], 'Featured')
        # Remaining videos should be in grid
        self.assertEqual(len(context['grid_videos']), 2)
        self.assertEqual(context['grid_videos'][0]['title'], 'Grid 1')
        self.assertEqual(context['grid_videos'][1]['title'], 'Grid 2')
        # All grid videos should have embed_url
        for video in context['grid_videos']:
            self.assertIn('embed_url', video)

    @patch('wagtail.embeds.embeds.get_embed')
    def test_all_videos_in_grid_when_featured_disabled(self, mock_get_embed):
        """Test that all videos go to grid when show_featured is False"""
        block = VideoFeedBlock()
        
        # Create mock embeds
        embeds = [self._create_mock_embed(title=f'Video {i}') for i in range(3)]
        mock_get_embed.side_effect = [embed[1] for embed in embeds]
        
        videos = [
            {'video': embeds[i][0], 'overrides': {}}
            for i in range(3)
        ]
        
        value = {
            'title': 'My Videos',
            'videos': videos,
            'show_featured': False,
            'grid_columns': '3',
        }
        
        context = block.get_context(value)
        
        # No featured video
        self.assertIsNone(context['featured_video'])
        # All videos in grid
        self.assertEqual(len(context['grid_videos']), 3)

    def test_handles_empty_video_list(self):
        """Test graceful handling of empty video list"""
        block = VideoFeedBlock()
        
        value = {
            'title': 'My Videos',
            'videos': [],
            'show_featured': True,
            'grid_columns': '4',
        }
        
        context = block.get_context(value)
        
        self.assertIsNone(context['featured_video'])
        self.assertEqual(len(context['grid_videos']), 0)

    @patch('wagtail.embeds.embeds.get_embed')
    def test_handles_single_video_with_featured_enabled(self, mock_get_embed):
        """Test that single video becomes featured, leaving empty grid"""
        block = VideoFeedBlock()
        
        embed_value, embed = self._create_mock_embed()
        mock_get_embed.return_value = embed
        
        single_video = {'video': embed_value, 'overrides': {}}
        
        value = {
            'title': 'My Videos',
            'videos': [single_video],
            'show_featured': True,
            'grid_columns': '4',
        }
        
        context = block.get_context(value)
        
        self.assertIsNotNone(context['featured_video'])
        self.assertIn('embed_url', context['featured_video'])
        self.assertEqual(len(context['grid_videos']), 0)

    def test_calculates_column_class_correctly(self):
        """Test that Bootstrap column classes are calculated correctly"""
        block = VideoFeedBlock()
        
        test_cases = [
            ('2', 'col-lg-6'),  # 12 / 2 = 6
            ('3', 'col-lg-4'),  # 12 / 3 = 4
            ('4', 'col-lg-3'),  # 12 / 4 = 3
        ]
        
        for columns, expected_class in test_cases:
            with self.subTest(columns=columns):
                value = {
                    'videos': [],
                    'show_featured': False,
                    'grid_columns': columns,
                }
                
                context = block.get_context(value)
                self.assertEqual(context['col_class'], expected_class)

    def test_context_includes_all_expected_keys(self):
        """Test that context has all expected keys"""
        block = VideoFeedBlock()
        
        value = {
            'title': 'Test',
            'videos': [
                {'video': self._create_mock_embed(), 'overrides': {}}
            ],
            'show_featured': True,
            'grid_columns': '4',
        }
        
        context = block.get_context(value)
        
        # Check for expected context keys
        self.assertIn('featured_video', context)
        self.assertIn('grid_videos', context)
        self.assertIn('col_class', context)
        
        # Also should have the original value
        self.assertIn('value', context)


class VideoFeedBlockMetaTests(TestCase):
    """Test cases for VideoFeedBlock Meta configuration"""

    def test_has_template(self):
        """Test that block has template configured"""
        block = VideoFeedBlock()
        self.assertEqual(block.meta.template, 'blocks/video_feed_block.html')

    def test_has_icon(self):
        """Test that block has icon configured"""
        block = VideoFeedBlock()
        self.assertEqual(block.meta.icon, 'bi-play-circle')

    def test_has_label(self):
        """Test that block has label configured"""
        block = VideoFeedBlock()
        self.assertEqual(block.meta.label, 'Video Feed')


class VideoFeedBlockEmbedUrlTests(TestCase):
    """Tests for _get_embed_data method"""
    
    def _create_mock_embed_with_html(self, url, html):
        """Helper to create a mock EmbedValue with custom HTML"""
        mock_embed_value = Mock()
        mock_embed_value.url = url
        
        # Mock the actual Embed object returned by embeds.get_embed()
        mock_embed = Mock()
        mock_embed.html = html
        mock_embed.thumbnail_url = 'https://example.com/thumb.jpg'
        mock_embed.title = 'Test Video'
        mock_embed.author_name = 'Test Author'
        mock_embed.provider_name = 'Test Provider'
        
        return mock_embed_value, mock_embed
    
    @patch('wagtail.embeds.embeds.get_embed')
    def test_extracts_youtube_embed_url_from_html(self, mock_get_embed):
        """Test extracting YouTube embed URL from iframe HTML"""
        block = VideoFeedBlock()
        mock_embed_value, mock_embed = self._create_mock_embed_with_html(
            url='https://www.youtube.com/watch?v=abc123',
            html='<iframe src="https://www.youtube.com/embed/abc123" frameborder="0" allowfullscreen></iframe>'
        )
        mock_get_embed.return_value = mock_embed
        
        result = block._get_embed_data(mock_embed_value)
        self.assertIsNotNone(result)
        self.assertEqual(result['embed_url'], 'https://www.youtube.com/embed/abc123')
    
    @patch('wagtail.embeds.embeds.get_embed')
    def test_extracts_vimeo_embed_url_from_html(self, mock_get_embed):
        """Test extracting Vimeo embed URL from iframe HTML"""
        block = VideoFeedBlock()
        mock_embed_value, mock_embed = self._create_mock_embed_with_html(
            url='https://vimeo.com/123456',
            html='<iframe src="https://player.vimeo.com/video/123456" frameborder="0" allowfullscreen></iframe>'
        )
        mock_get_embed.return_value = mock_embed
        
        result = block._get_embed_data(mock_embed_value)
        self.assertIsNotNone(result)
        self.assertEqual(result['embed_url'], 'https://player.vimeo.com/video/123456')
    
    @patch('wagtail.embeds.embeds.get_embed')
    def test_constructs_youtube_watch_url(self, mock_get_embed):
        """Test constructing embed URL from YouTube watch URL when HTML parsing fails"""
        block = VideoFeedBlock()
        mock_embed_value = Mock()
        mock_embed_value.url = 'https://www.youtube.com/watch?v=xyz789'
        
        mock_embed = Mock()
        mock_embed.html = ''  # Empty HTML to force URL construction
        mock_embed.thumbnail_url = 'https://example.com/thumb.jpg'
        mock_embed.title = 'Test Video'
        mock_embed.author_name = 'Test Author'
        mock_embed.provider_name = 'YouTube'
        mock_get_embed.return_value = mock_embed
        
        result = block._get_embed_data(mock_embed_value)
        self.assertIsNotNone(result)
        self.assertEqual(result['embed_url'], 'https://www.youtube.com/embed/xyz789')
    
    @patch('wagtail.embeds.embeds.get_embed')
    def test_constructs_youtube_short_url(self, mock_get_embed):
        """Test constructing embed URL from youtu.be short URL"""
        block = VideoFeedBlock()
        mock_embed_value = Mock()
        mock_embed_value.url = 'https://youtu.be/short123'
        
        mock_embed = Mock()
        mock_embed.html = ''
        mock_embed.thumbnail_url = 'https://example.com/thumb.jpg'
        mock_embed.title = 'Test Video'
        mock_embed.author_name = 'Test Author'
        mock_embed.provider_name = 'YouTube'
        mock_get_embed.return_value = mock_embed
        
        result = block._get_embed_data(mock_embed_value)
        self.assertIsNotNone(result)
        self.assertEqual(result['embed_url'], 'https://www.youtube.com/embed/short123')
    
    @patch('wagtail.embeds.embeds.get_embed')
    def test_constructs_vimeo_url(self, mock_get_embed):
        """Test constructing embed URL from Vimeo URL"""
        block = VideoFeedBlock()
        mock_embed_value = Mock()
        mock_embed_value.url = 'https://vimeo.com/987654'
        
        mock_embed = Mock()
        mock_embed.html = ''
        mock_embed.thumbnail_url = 'https://example.com/thumb.jpg'
        mock_embed.title = 'Test Video'
        mock_embed.author_name = 'Test Author'
        mock_embed.provider_name = 'Vimeo'
        mock_get_embed.return_value = mock_embed
        
        result = block._get_embed_data(mock_embed_value)
        self.assertIsNotNone(result)
        self.assertEqual(result['embed_url'], 'https://player.vimeo.com/video/987654')
    
    def test_returns_none_for_invalid_embed(self):
        """Test that None is returned for None embed"""
        block = VideoFeedBlock()
        result = block._get_embed_data(None)
        self.assertIsNone(result)
