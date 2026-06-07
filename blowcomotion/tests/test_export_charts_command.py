"""
Tests for the export_charts_to_csv management command.
"""
import csv
import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from blowcomotion.models import Chart, Instrument, Song


class ExportChartsToCSVCommandTest(TestCase):
    """Tests for the export_charts_to_csv management command."""

    def test_export_charts_to_csv_with_existing_data(self):
        """Test basic CSV export functionality with existing database data."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as tmp:
            tmp_path = tmp.name

        try:
            out = StringIO()
            call_command('export_charts_to_csv', output_path=tmp_path, stdout=out)

            # Verify file was created
            self.assertTrue(os.path.exists(tmp_path))

            # Read and verify CSV content
            with open(tmp_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                rows = list(reader)

            # Verify headers exist
            if len(rows) > 0:
                expected_headers = [
                    'id',
                    'song_id',
                    'song_title',
                    'instrument_id',
                    'instrument_name',
                    'part',
                    'pdf_id',
                    'pdf_title',
                ]
                self.assertEqual(list(rows[0].keys()), expected_headers)

                # Verify data structure of first row
                self.assertIn('id', rows[0])
                self.assertIn('song_title', rows[0])
                self.assertIn('instrument_name', rows[0])

            # Verify command output
            output = out.getvalue()
            self.assertIn('written to', output)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_export_charts_default_output_path(self):
        """Test export with default output path."""
        default_path = 'charts_export.csv'
        
        try:
            out = StringIO()
            call_command('export_charts_to_csv', stdout=out)

            # Verify file was created at default location
            self.assertTrue(os.path.exists(default_path))

            # Verify command output
            output = out.getvalue()
            self.assertIn('Export complete', output)

        finally:
            if os.path.exists(default_path):
                os.remove(default_path)

    def test_export_charts_empty_database(self):
        """Test export when no charts exist."""
        # Get current chart count
        initial_count = Chart.objects.count()
        
        # Delete all charts
        Chart.objects.all().delete()

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as tmp:
            tmp_path = tmp.name

        try:
            out = StringIO()
            call_command('export_charts_to_csv', output_path=tmp_path, stdout=out)

            # Verify file was created with just headers
            with open(tmp_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                rows = list(reader)

            # Should have headers but no data rows
            self.assertEqual(len(rows), 1)
            
            # Verify warning message
            output = out.getvalue()
            self.assertIn('No charts found', output)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_export_charts_with_subdirectory(self):
        """Test export to a path with subdirectories that don't exist yet."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'subdir', 'charts.csv')
            
            out = StringIO()
            call_command('export_charts_to_csv', output_path=output_path, stdout=out)

            # Verify file was created (directory should be created automatically)
            self.assertTrue(os.path.exists(output_path))
            
            # Verify content has headers
            with open(output_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                headers = next(reader)
            
            # Verify we have the expected headers
            expected_headers = [
                'id',
                'song_id',
                'song_title',
                'instrument_id',
                'instrument_name',
                'part',
                'pdf_id',
                'pdf_title',
            ]
            self.assertEqual(headers, expected_headers)

    def test_export_charts_csv_format(self):
        """Test that the CSV has proper format and required columns."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as tmp:
            tmp_path = tmp.name

        try:
            call_command('export_charts_to_csv', output_path=tmp_path, stdout=StringIO())

            with open(tmp_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                headers = reader.fieldnames
                
                # Verify all required headers are present
                required_headers = [
                    'id',
                    'song_id',
                    'song_title',
                    'instrument_id',
                    'instrument_name',
                    'part',
                    'pdf_id',
                    'pdf_title',
                ]
                
                for header in required_headers:
                    self.assertIn(header, headers)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

