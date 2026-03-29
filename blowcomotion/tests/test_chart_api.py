"""
Unit tests for Chart Library API endpoints.
"""

from wagtail.documents.models import Document

from django.test import Client, TestCase
from django.urls import reverse

from blowcomotion.models import Chart, Instrument, Section, Song


class SongsWithChartsEndpointTests(TestCase):
    """Test cases for the songs_with_charts API endpoint"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()

        # Create test sections and instruments
        self.woodwinds = Section.objects.create(name="Woodwinds")
        self.brass = Section.objects.create(name="Brass")
        
        self.clarinet = Instrument.objects.create(
            name="Clarinet",
            section=self.woodwinds
        )
        self.trumpet = Instrument.objects.create(
            name="Trumpet",
            section=self.brass
        )

        # Create test documents (PDFs)
        self.pdf1 = Document.objects.create(
            title="Test Chart 1",
            file="test1.pdf"
        )
        self.pdf2 = Document.objects.create(
            title="Test Chart 2",
            file="test2.pdf"
        )

        # Create active song with charts
        self.song_with_charts = Song.objects.create(
            title="Song With Charts",
            active=True
        )
        Chart.objects.create(
            song=self.song_with_charts,
            instrument=self.clarinet,
            pdf=self.pdf1,
            part="1st Clarinet"
        )

        # Create active song without charts
        self.song_without_charts = Song.objects.create(
            title="Song Without Charts",
            active=True
        )

        # Create active song with charts but no PDFs
        self.song_no_pdfs = Song.objects.create(
            title="Song No PDFs",
            active=True
        )
        Chart.objects.create(
            song=self.song_no_pdfs,
            instrument=self.clarinet,
            pdf=None,
            part="1st Clarinet"
        )

        # Create inactive song with charts
        self.inactive_song = Song.objects.create(
            title="Inactive Song",
            active=False
        )
        Chart.objects.create(
            song=self.inactive_song,
            instrument=self.trumpet,
            pdf=self.pdf2,
            part="1st Trumpet"
        )

    def test_songs_endpoint_returns_only_active_with_pdfs(self):
        """Test that endpoint only returns active songs that have charts with PDFs"""
        response = self.client.get(reverse('chart-songs'))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('songs', data)
        self.assertEqual(len(data['songs']), 1)
        self.assertEqual(data['songs'][0]['title'], 'Song With Charts')

    def test_songs_endpoint_search_filter(self):
        """Test search filtering by song title"""
        # Create another song with chart
        searchable_song = Song.objects.create(
            title="Jazz Funeral",
            active=True
        )
        Chart.objects.create(
            song=searchable_song,
            instrument=self.trumpet,
            pdf=self.pdf2,
            part="Trumpet"
        )
        
        response = self.client.get(reverse('chart-songs'), {'search': 'jazz'})
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(len(data['songs']), 1)
        self.assertEqual(data['songs'][0]['title'], 'Jazz Funeral')

    def test_songs_endpoint_case_insensitive_search(self):
        """Test that search is case-insensitive"""
        response = self.client.get(reverse('chart-songs'), {'search': 'SONG WITH'})
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(len(data['songs']), 1)
        self.assertEqual(data['songs'][0]['title'], 'Song With Charts')

    def test_songs_endpoint_empty_results(self):
        """Test response when search returns no results"""
        response = self.client.get(reverse('chart-songs'), {'search': 'nonexistent'})
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('songs', data)
        self.assertEqual(len(data['songs']), 0)

    def test_songs_endpoint_includes_recording_info(self):
        """Test that response includes recording availability"""
        response = self.client.get(reverse('chart-songs'))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        song_data = data['songs'][0]
        self.assertIn('has_recording', song_data)
        self.assertIn('id', song_data)
        self.assertIn('title', song_data)

    def test_songs_endpoint_includes_video_info(self):
        """Test that response includes video availability"""
        # Create song with video
        from blowcomotion.models import SongVideo
        song_video = SongVideo.objects.create(
            song=self.song_with_charts,
            url="https://youtube.com/watch?v=test",
            title="Test Video"
        )
        
        response = self.client.get(reverse('chart-songs'))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        song_data = data['songs'][0]
        self.assertIn('has_video', song_data)
        self.assertTrue(song_data['has_video'])
        self.assertIn('videos', song_data)
        self.assertEqual(len(song_data['videos']), 1)
        self.assertEqual(song_data['videos'][0]['url'], "https://youtube.com/watch?v=test")
        self.assertEqual(song_data['videos'][0]['title'], "Test Video")

    def test_songs_endpoint_multiple_videos(self):
        """Test that response includes multiple videos per song"""
        from blowcomotion.models import SongVideo
        SongVideo.objects.create(
            song=self.song_with_charts,
            url="https://youtube.com/watch?v=test1",
            title="Video 1"
        )
        SongVideo.objects.create(
            song=self.song_with_charts,
            url="https://youtube.com/watch?v=test2",
            title="Video 2"
        )
        
        response = self.client.get(reverse('chart-songs'))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        song_data = data['songs'][0]
        self.assertEqual(len(song_data['videos']), 2)


class InstrumentsForSongEndpointTests(TestCase):
    """Test cases for the instruments_for_song API endpoint"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()

        # Create test sections and instruments
        self.woodwinds = Section.objects.create(name="Woodwinds")
        self.brass = Section.objects.create(name="Brass")
        
        self.clarinet = Instrument.objects.create(
            name="Clarinet",
            section=self.woodwinds
        )
        self.saxophone = Instrument.objects.create(
            name="Saxophone",
            section=self.woodwinds
        )
        self.trumpet = Instrument.objects.create(
            name="Trumpet",
            section=self.brass
        )
        self.trombone = Instrument.objects.create(
            name="Trombone",
            section=self.brass
        )

        # Create test document
        self.pdf = Document.objects.create(
            title="Test Chart",
            file="test.pdf"
        )

        # Create test song
        self.song = Song.objects.create(
            title="Test Song",
            active=True
        )

        # Create charts for multiple instruments
        Chart.objects.create(
            song=self.song,
            instrument=self.clarinet,
            pdf=self.pdf,
            part="Clarinet"
        )
        Chart.objects.create(
            song=self.song,
            instrument=self.trumpet,
            pdf=self.pdf,
            part="Trumpet"
        )
        Chart.objects.create(
            song=self.song,
            instrument=self.trombone,
            pdf=self.pdf,
            part="Trombone"
        )

        # Create inactive song
        self.inactive_song = Song.objects.create(
            title="Inactive Song",
            active=False
        )
        Chart.objects.create(
            song=self.inactive_song,
            instrument=self.saxophone,
            pdf=self.pdf,
            part="Saxophone"
        )

    def test_instruments_endpoint_success(self):
        """Test successful retrieval of instruments for a song"""
        response = self.client.get(
            reverse('chart-instruments', kwargs={'song_id': self.song.id})
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('sections', data)
        self.assertEqual(data['song_id'], self.song.id)
        self.assertEqual(data['song_title'], 'Test Song')

    def test_instruments_grouped_by_section(self):
        """Test that instruments are grouped by section"""
        response = self.client.get(
            reverse('chart-instruments', kwargs={'song_id': self.song.id})
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        sections = data['sections']
        
        # Should have 2 sections (Woodwinds and Brass)
        self.assertEqual(len(sections), 2)
        
        # Find brass section
        brass_section = next(s for s in sections if s['name'] == 'Brass')
        self.assertEqual(len(brass_section['instruments']), 2)
        instrument_names = [i['name'] for i in brass_section['instruments']]
        self.assertIn('Trumpet', instrument_names)
        self.assertIn('Trombone', instrument_names)

    def test_instruments_only_with_pdfs(self):
        """Test that only instruments with PDF charts are returned"""
        # Create chart without PDF
        Chart.objects.create(
            song=self.song,
            instrument=self.saxophone,
            pdf=None,
            part="Saxophone"
        )
        
        response = self.client.get(
            reverse('chart-instruments', kwargs={'song_id': self.song.id})
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        
        # Saxophone should not appear because it has no PDF
        all_instruments = []
        for section in data['sections']:
            all_instruments.extend([i['name'] for i in section['instruments']])
        self.assertNotIn('Saxophone', all_instruments)

    def test_instruments_nonexistent_song(self):
        """Test 404 response for nonexistent song"""
        response = self.client.get(
            reverse('chart-instruments', kwargs={'song_id': 99999})
        )
        self.assertEqual(response.status_code, 404)
        
        data = response.json()
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Song not found')

    def test_instruments_inactive_song(self):
        """Test 404 response for inactive song"""
        response = self.client.get(
            reverse('chart-instruments', kwargs={'song_id': self.inactive_song.id})
        )
        self.assertEqual(response.status_code, 404)
        
        data = response.json()
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Song not found')

    def test_instruments_empty_results(self):
        """Test response when song has no instruments with charts"""
        empty_song = Song.objects.create(
            title="Empty Song",
            active=True
        )
        
        response = self.client.get(
            reverse('chart-instruments', kwargs={'song_id': empty_song.id})
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(len(data['sections']), 0)


class ChartsForSongInstrumentEndpointTests(TestCase):
    """Test cases for the charts_for_song_instrument API endpoint"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()

        # Create test section and instrument
        self.section = Section.objects.create(name="Test Section")
        self.instrument = Instrument.objects.create(
            name="Test Instrument",
            section=self.section
        )
        self.other_instrument = Instrument.objects.create(
            name="Other Instrument",
            section=self.section
        )

        # Create test documents
        self.pdf1 = Document.objects.create(
            title="Chart Part 1",
            file="chart1.pdf"
        )
        self.pdf2 = Document.objects.create(
            title="Chart Part 2",
            file="chart2.pdf"
        )

        # Create test song
        self.song = Song.objects.create(
            title="Test Song",
            active=True
        )

        # Create multiple chart parts for the same instrument
        self.chart1 = Chart.objects.create(
            song=self.song,
            instrument=self.instrument,
            pdf=self.pdf1,
            part="1st Part"
        )
        self.chart2 = Chart.objects.create(
            song=self.song,
            instrument=self.instrument,
            pdf=self.pdf2,
            part="2nd Part"
        )

        # Create chart for different instrument
        Chart.objects.create(
            song=self.song,
            instrument=self.other_instrument,
            pdf=self.pdf1,
            part="Other Part"
        )

        # Create inactive song
        self.inactive_song = Song.objects.create(
            title="Inactive Song",
            active=False
        )

    def test_charts_endpoint_success(self):
        """Test successful retrieval of charts for song and instrument"""
        response = self.client.get(
            reverse('chart-parts', kwargs={
                'song_id': self.song.id,
                'instrument_id': self.instrument.id
            })
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('charts', data)
        self.assertEqual(data['song_id'], self.song.id)
        self.assertEqual(data['song_title'], 'Test Song')
        self.assertEqual(data['instrument_id'], self.instrument.id)
        self.assertEqual(data['instrument_name'], 'Test Instrument')

    def test_charts_multiple_parts(self):
        """Test that multiple parts are returned for same instrument"""
        response = self.client.get(
            reverse('chart-parts', kwargs={
                'song_id': self.song.id,
                'instrument_id': self.instrument.id
            })
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(len(data['charts']), 2)
        
        chart_parts = [c['part'] for c in data['charts']]
        self.assertIn('1st Part', chart_parts)
        self.assertIn('2nd Part', chart_parts)

    def test_charts_include_pdf_info(self):
        """Test that charts include PDF URL and title"""
        response = self.client.get(
            reverse('chart-parts', kwargs={
                'song_id': self.song.id,
                'instrument_id': self.instrument.id
            })
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        chart = data['charts'][0]
        self.assertIn('id', chart)
        self.assertIn('part', chart)
        self.assertIn('pdf_url', chart)
        self.assertIn('pdf_title', chart)
        self.assertIsNotNone(chart['pdf_url'])

    def test_charts_only_for_specified_instrument(self):
        """Test that only charts for specified instrument are returned"""
        response = self.client.get(
            reverse('chart-parts', kwargs={
                'song_id': self.song.id,
                'instrument_id': self.instrument.id
            })
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        # Should only return 2 charts for self.instrument, not the chart for other_instrument
        self.assertEqual(len(data['charts']), 2)

    def test_charts_only_with_pdfs(self):
        """Test that only charts with PDFs are returned"""
        # Create chart without PDF
        Chart.objects.create(
            song=self.song,
            instrument=self.instrument,
            pdf=None,
            part="No PDF Part"
        )
        
        response = self.client.get(
            reverse('chart-parts', kwargs={
                'song_id': self.song.id,
                'instrument_id': self.instrument.id
            })
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        # Should still only return 2 charts (the ones with PDFs)
        self.assertEqual(len(data['charts']), 2)
        chart_parts = [c['part'] for c in data['charts']]
        self.assertNotIn('No PDF Part', chart_parts)

    def test_charts_nonexistent_song(self):
        """Test 404 response for nonexistent song"""
        response = self.client.get(
            reverse('chart-parts', kwargs={
                'song_id': 99999,
                'instrument_id': self.instrument.id
            })
        )
        self.assertEqual(response.status_code, 404)
        
        data = response.json()
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Song not found')

    def test_charts_inactive_song(self):
        """Test 404 response for inactive song"""
        response = self.client.get(
            reverse('chart-parts', kwargs={
                'song_id': self.inactive_song.id,
                'instrument_id': self.instrument.id
            })
        )
        self.assertEqual(response.status_code, 404)
        
        data = response.json()
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Song not found')

    def test_charts_nonexistent_instrument(self):
        """Test 404 response for nonexistent instrument"""
        response = self.client.get(
            reverse('chart-parts', kwargs={
                'song_id': self.song.id,
                'instrument_id': 99999
            })
        )
        self.assertEqual(response.status_code, 404)
        
        data = response.json()
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Instrument not found')

    def test_charts_empty_results(self):
        """Test response when no charts match the criteria"""
        empty_instrument = Instrument.objects.create(
            name="Empty Instrument",
            section=self.section
        )
        
        response = self.client.get(
            reverse('chart-parts', kwargs={
                'song_id': self.song.id,
                'instrument_id': empty_instrument.id
            })
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(len(data['charts']), 0)

    def test_charts_default_part_name(self):
        """Test that part name defaults to instrument name if not specified"""
        # Create chart with no part specified
        chart_no_part = Chart.objects.create(
            song=self.song,
            instrument=self.instrument,
            pdf=self.pdf1,
            part=""  # Empty part
        )
        
        response = self.client.get(
            reverse('chart-parts', kwargs={
                'song_id': self.song.id,
                'instrument_id': self.instrument.id
            })
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        # One of the charts should have part name equal to instrument name
        part_names = [c['part'] for c in data['charts']]
        self.assertIn('Test Instrument', part_names)


class InstrumentsWithChartsEndpointTests(TestCase):
    """Test cases for the instruments_with_charts API endpoint"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()

        # Create test sections
        self.woodwinds = Section.objects.create(name="Woodwinds")
        self.brass = Section.objects.create(name="Brass")
        self.rhythm = Section.objects.create(name="Rhythm")
        
        # Create test instruments
        self.clarinet = Instrument.objects.create(
            name="Clarinet",
            section=self.woodwinds
        )
        self.saxophone = Instrument.objects.create(
            name="Saxophone",
            section=self.woodwinds
        )
        self.trumpet = Instrument.objects.create(
            name="Trumpet",
            section=self.brass
        )
        self.trombone = Instrument.objects.create(
            name="Trombone",
            section=self.brass
        )
        self.piano = Instrument.objects.create(
            name="Piano",
            section=self.rhythm
        )

        # Create test documents (PDFs)
        self.pdf1 = Document.objects.create(
            title="Test Chart 1",
            file="test1.pdf"
        )
        self.pdf2 = Document.objects.create(
            title="Test Chart 2",
            file="test2.pdf"
        )

        # Create active songs with charts
        self.active_song1 = Song.objects.create(
            title="Active Song 1",
            active=True
        )
        Chart.objects.create(
            song=self.active_song1,
            instrument=self.clarinet,
            pdf=self.pdf1,
            part="Clarinet"
        )
        Chart.objects.create(
            song=self.active_song1,
            instrument=self.trumpet,
            pdf=self.pdf1,
            part="Trumpet"
        )

        self.active_song2 = Song.objects.create(
            title="Active Song 2",
            active=True
        )
        Chart.objects.create(
            song=self.active_song2,
            instrument=self.trombone,
            pdf=self.pdf2,
            part="Trombone"
        )

        # Create inactive song with charts (should be excluded)
        self.inactive_song = Song.objects.create(
            title="Inactive Song",
            active=False
        )
        Chart.objects.create(
            song=self.inactive_song,
            instrument=self.saxophone,
            pdf=self.pdf2,
            part="Saxophone"
        )

        # Create chart without PDF (should be excluded)
        Chart.objects.create(
            song=self.active_song1,
            instrument=self.piano,
            pdf=None,
            part="Piano"
        )

    def test_instruments_endpoint_success(self):
        """Test successful retrieval of instruments with charts"""
        response = self.client.get(reverse('chart-instruments-list'))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('sections', data)

    def test_instruments_grouped_by_section(self):
        """Test that instruments are grouped by section"""
        response = self.client.get(reverse('chart-instruments-list'))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        sections = data['sections']
        
        # Should have 2 sections (Woodwinds and Brass), not Rhythm (piano has no PDF)
        self.assertEqual(len(sections), 2)
        
        section_names = [s['name'] for s in sections]
        self.assertIn('Woodwinds', section_names)
        self.assertIn('Brass', section_names)
        self.assertNotIn('Rhythm', section_names)

    def test_instruments_only_with_pdfs(self):
        """Test that only instruments with PDF charts are returned"""
        response = self.client.get(reverse('chart-instruments-list'))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        
        # Collect all instrument names
        all_instruments = []
        for section in data['sections']:
            all_instruments.extend([i['name'] for i in section['instruments']])
        
        # Piano should not appear (has chart but no PDF)
        self.assertNotIn('Piano', all_instruments)
        
        # These should appear
        self.assertIn('Clarinet', all_instruments)
        self.assertIn('Trumpet', all_instruments)
        self.assertIn('Trombone', all_instruments)

    def test_instruments_only_for_active_songs(self):
        """Test that instruments are excluded if all their charts belong to inactive songs"""
        response = self.client.get(reverse('chart-instruments-list'))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        
        # Collect all instrument names
        all_instruments = []
        for section in data['sections']:
            all_instruments.extend([i['name'] for i in section['instruments']])
        
        # Saxophone should not appear (only has charts for inactive songs)
        self.assertNotIn('Saxophone', all_instruments)

    def test_instruments_section_structure(self):
        """Test that sections have correct structure"""
        response = self.client.get(reverse('chart-instruments-list'))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        sections = data['sections']
        
        for section in sections:
            self.assertIn('id', section)
            self.assertIn('name', section)
            self.assertIn('instruments', section)
            
            for instrument in section['instruments']:
                self.assertIn('id', instrument)
                self.assertIn('name', instrument)

    def test_instruments_sorted_by_section_and_name(self):
        """Test that sections and instruments are properly sorted"""
        response = self.client.get(reverse('chart-instruments-list'))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        sections = data['sections']
        
        # Sections should be sorted alphabetically
        section_names = [s['name'] for s in sections]
        self.assertEqual(section_names, sorted(section_names))
        
        # Find brass section and check instrument sorting
        brass_section = next(s for s in sections if s['name'] == 'Brass')
        instrument_names = [i['name'] for i in brass_section['instruments']]
        self.assertEqual(instrument_names, sorted(instrument_names))

    def test_instruments_empty_results(self):
        """Test response when no instruments have charts with PDFs for active songs"""
        # Delete all charts
        Chart.objects.all().delete()
        
        response = self.client.get(reverse('chart-instruments-list'))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('sections', data)
        self.assertEqual(len(data['sections']), 0)


class SongsForInstrumentEndpointTests(TestCase):
    """Test cases for the songs_for_instrument API endpoint"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()

        # Create test section and instruments
        self.section = Section.objects.create(name="Test Section")
        self.clarinet = Instrument.objects.create(
            name="Clarinet",
            section=self.section
        )
        self.trumpet = Instrument.objects.create(
            name="Trumpet",
            section=self.section
        )

        # Create test documents
        self.pdf1 = Document.objects.create(
            title="Chart Part 1",
            file="chart1.pdf"
        )
        self.pdf2 = Document.objects.create(
            title="Chart Part 2",
            file="chart2.pdf"
        )
        self.pdf3 = Document.objects.create(
            title="Chart Part 3",
            file="chart3.pdf"
        )

        # Create active songs with charts
        self.song1 = Song.objects.create(
            title="Test Song 1",
            active=True
        )
        Chart.objects.create(
            song=self.song1,
            instrument=self.clarinet,
            pdf=self.pdf1,
            part="1st Clarinet"
        )

        self.song2 = Song.objects.create(
            title="Test Song 2",
            active=True
        )
        Chart.objects.create(
            song=self.song2,
            instrument=self.clarinet,
            pdf=self.pdf2,
            part="Clarinet"
        )

        # Song with multiple parts for same instrument
        self.song_multi_parts = Song.objects.create(
            title="Multi Part Song",
            active=True
        )
        Chart.objects.create(
            song=self.song_multi_parts,
            instrument=self.clarinet,
            pdf=self.pdf1,
            part="1st Clarinet"
        )
        Chart.objects.create(
            song=self.song_multi_parts,
            instrument=self.clarinet,
            pdf=self.pdf2,
            part="2nd Clarinet"
        )

        # Inactive song (should be excluded)
        self.inactive_song = Song.objects.create(
            title="Inactive Song",
            active=False
        )
        Chart.objects.create(
            song=self.inactive_song,
            instrument=self.clarinet,
            pdf=self.pdf3,
            part="Clarinet"
        )

        # Song with chart but no PDF (should be excluded)
        self.song_no_pdf = Song.objects.create(
            title="Song No PDF",
            active=True
        )
        Chart.objects.create(
            song=self.song_no_pdf,
            instrument=self.clarinet,
            pdf=None,
            part="Clarinet"
        )

        # Song for different instrument
        self.other_song = Song.objects.create(
            title="Trumpet Song",
            active=True
        )
        Chart.objects.create(
            song=self.other_song,
            instrument=self.trumpet,
            pdf=self.pdf1,
            part="Trumpet"
        )

    def test_songs_endpoint_success(self):
        """Test successful retrieval of songs for an instrument"""
        response = self.client.get(
            reverse('chart-songs-for-instrument', kwargs={'instrument_id': self.clarinet.id})
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('songs', data)
        self.assertEqual(data['instrument_id'], self.clarinet.id)
        self.assertEqual(data['instrument_name'], 'Clarinet')

    def test_songs_only_active_with_pdfs(self):
        """Test that only active songs with PDF charts are returned"""
        response = self.client.get(
            reverse('chart-songs-for-instrument', kwargs={'instrument_id': self.clarinet.id})
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        songs = data['songs']
        
        # Should have 3 songs (song1, song2, song_multi_parts)
        # Should NOT include: inactive_song, song_no_pdf, other_song
        self.assertEqual(len(songs), 3)
        
        song_titles = [s['title'] for s in songs]
        self.assertIn('Test Song 1', song_titles)
        self.assertIn('Test Song 2', song_titles)
        self.assertIn('Multi Part Song', song_titles)
        self.assertNotIn('Inactive Song', song_titles)
        self.assertNotIn('Song No PDF', song_titles)
        self.assertNotIn('Trumpet Song', song_titles)

    def test_songs_include_charts_data(self):
        """Test that songs include their chart data inline"""
        response = self.client.get(
            reverse('chart-songs-for-instrument', kwargs={'instrument_id': self.clarinet.id})
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        
        # Find the multi-part song
        multi_part = next(s for s in data['songs'] if s['title'] == 'Multi Part Song')
        
        self.assertIn('charts', multi_part)
        self.assertEqual(len(multi_part['charts']), 2)
        
        # Check chart structure
        chart = multi_part['charts'][0]
        self.assertIn('id', chart)
        self.assertIn('part', chart)
        self.assertIn('pdf_url', chart)
        self.assertIn('pdf_title', chart)
        
        # Check part names
        part_names = [c['part'] for c in multi_part['charts']]
        self.assertIn('1st Clarinet', part_names)
        self.assertIn('2nd Clarinet', part_names)

    def test_songs_include_recording_info(self):
        """Test that songs include recording information"""
        response = self.client.get(
            reverse('chart-songs-for-instrument', kwargs={'instrument_id': self.clarinet.id})
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        song = data['songs'][0]
        
        self.assertIn('has_recording', song)
        self.assertIn('id', song)
        self.assertIn('title', song)

    def test_songs_include_video_info(self):
        """Test that songs include video information"""
        from blowcomotion.models import SongVideo

        # Add video to song1
        SongVideo.objects.create(
            song=self.song1,
            url="https://youtube.com/watch?v=test",
            title="Test Video"
        )
        
        response = self.client.get(
            reverse('chart-songs-for-instrument', kwargs={'instrument_id': self.clarinet.id})
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        song_with_video = next(s for s in data['songs'] if s['title'] == 'Test Song 1')
        
        self.assertIn('has_video', song_with_video)
        self.assertTrue(song_with_video['has_video'])
        self.assertIn('videos', song_with_video)
        self.assertEqual(len(song_with_video['videos']), 1)
        self.assertEqual(song_with_video['videos'][0]['url'], "https://youtube.com/watch?v=test")
        self.assertEqual(song_with_video['videos'][0]['title'], "Test Video")

    def test_songs_search_filter(self):
        """Test search filtering by song title"""
        response = self.client.get(
            reverse('chart-songs-for-instrument', kwargs={'instrument_id': self.clarinet.id}),
            {'search': 'Multi'}
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(len(data['songs']), 1)
        self.assertEqual(data['songs'][0]['title'], 'Multi Part Song')

    def test_songs_search_case_insensitive(self):
        """Test that search is case-insensitive"""
        response = self.client.get(
            reverse('chart-songs-for-instrument', kwargs={'instrument_id': self.clarinet.id}),
            {'search': 'TEST SONG'}
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        # Should match both "Test Song 1" and "Test Song 2"
        self.assertEqual(len(data['songs']), 2)

    def test_songs_search_empty_results(self):
        """Test response when search returns no results"""
        response = self.client.get(
            reverse('chart-songs-for-instrument', kwargs={'instrument_id': self.clarinet.id}),
            {'search': 'nonexistent'}
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('songs', data)
        self.assertEqual(len(data['songs']), 0)

    def test_songs_nonexistent_instrument(self):
        """Test 404 response for nonexistent instrument"""
        response = self.client.get(
            reverse('chart-songs-for-instrument', kwargs={'instrument_id': 99999})
        )
        self.assertEqual(response.status_code, 404)
        
        data = response.json()
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Instrument not found')

    def test_songs_sorted_by_title(self):
        """Test that songs are sorted alphabetically by title"""
        response = self.client.get(
            reverse('chart-songs-for-instrument', kwargs={'instrument_id': self.clarinet.id})
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        song_titles = [s['title'] for s in data['songs']]
        self.assertEqual(song_titles, sorted(song_titles))

    def test_songs_empty_results(self):
        """Test response when instrument has no songs with charts"""
        empty_instrument = Instrument.objects.create(
            name="Empty Instrument",
            section=self.section
        )
        
        response = self.client.get(
            reverse('chart-songs-for-instrument', kwargs={'instrument_id': empty_instrument.id})
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(len(data['songs']), 0)

    def test_songs_no_n_plus_one_queries(self):
        """Test that charts are prefetched efficiently (no N+1 queries)"""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                reverse('chart-songs-for-instrument', kwargs={'instrument_id': self.clarinet.id})
            )
            self.assertEqual(response.status_code, 200)
        
        # Should use a fixed number of queries regardless of song count:
        # 1. Get instrument
        # 2. Get song IDs with charts
        # 3. Get songs with prefetch
        # 4. Prefetch videos
        # 5. Prefetch charts
        # Should NOT have one query per song for charts
        query_count = len(queries)
        self.assertLessEqual(query_count, 6, 
            f"Expected ≤6 queries, got {query_count}. Possible N+1 query issue.")
