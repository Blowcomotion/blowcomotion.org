"""
Tests for the export_library_instruments_to_csv management command.
"""
import csv
import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from blowcomotion.models import LibraryInstrument


class ExportLibraryInstrumentsToCSVCommandTest(TestCase):
    """Tests for the export_library_instruments_to_csv management command."""

    def setUp(self):
        import datetime
        from decimal import Decimal

        from blowcomotion.models import Instrument, Member

        instrument = Instrument.objects.create(name="Trombone")
        member = Member.objects.create(first_name="Ada", last_name="Lovelace")

        LibraryInstrument.objects.create(
            instrument=instrument,
            status=LibraryInstrument.STATUS_RENTED,
            serial_number="SN123",
            member=member,
            rental_date=datetime.date(2026, 1, 2),
            acquisition_cost=Decimal("0.00"),
            current_value=Decimal("123.45"),
            replacement_cost=Decimal("0.00"),
            patreon_active=False,
            patreon_amount=Decimal("0.00"),
            comments="Test export",
        )
    def test_export_library_instruments_to_csv_with_existing_data(self):
        """Test basic CSV export functionality with existing database data."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as tmp:
            tmp_path = tmp.name

        try:
            out = StringIO()
            call_command('export_library_instruments_to_csv', output_path=tmp_path, stdout=out)

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
                    'instrument_id',
                    'instrument_name',
                    'status',
                    'status_display',
                    'serial_number',
                    'member_id',
                    'member_name',
                    'rental_date',
                    'acquisition_cost',
                    'current_value',
                    'replacement_cost',
                    'patreon_active',
                    'patreon_amount',
                    'storage_location_id',
                    'storage_location_name',
                    'comments',
                    'created_at',
                    'updated_at',
                ]
                self.assertEqual(list(rows[0].keys()), expected_headers)

                # Verify data structure of first row (including 0.00 values)
                self.assertEqual(rows[0]["instrument_name"], "Trombone")
                self.assertEqual(rows[0]["status"], LibraryInstrument.STATUS_RENTED)
                self.assertEqual(rows[0]["acquisition_cost"], "0.00")
                self.assertEqual(rows[0]["replacement_cost"], "0.00")
                self.assertEqual(rows[0]["patreon_amount"], "0.00")
            # Verify command output
            output = out.getvalue()
            self.assertIn('written to', output)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_export_library_instruments_default_output_path(self):
        """Test export with default output path."""
        default_path = 'library_instruments_export.csv'
        
        try:
            out = StringIO()
            call_command('export_library_instruments_to_csv', stdout=out)

            # Verify file was created at default location
            self.assertTrue(os.path.exists(default_path))

            # Verify command output
            output = out.getvalue()
            self.assertIn('Export complete', output)

        finally:
            if os.path.exists(default_path):
                os.remove(default_path)

    def test_export_library_instruments_empty_database(self):
        """Test export when no library instruments exist."""
        # Ensure database is empty
        # Delete all library instruments
        LibraryInstrument.objects.all().delete()

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as tmp:
            tmp_path = tmp.name

        try:
            out = StringIO()
            call_command('export_library_instruments_to_csv', output_path=tmp_path, stdout=out)

            # Verify file was created with just headers
            with open(tmp_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                rows = list(reader)

            # Should have headers but no data rows
            self.assertEqual(len(rows), 1)
            
            # Verify warning message
            output = out.getvalue()
            self.assertIn('No library instruments found', output)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_export_library_instruments_with_subdirectory(self):
        """Test export to a path with subdirectories that don't exist yet."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'subdir', 'library_instruments.csv')
            
            out = StringIO()
            call_command('export_library_instruments_to_csv', output_path=output_path, stdout=out)

            # Verify file was created (directory should be created automatically)
            self.assertTrue(os.path.exists(output_path))
            
            # Verify content has headers
            with open(output_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                headers = next(reader)
            
            # Verify we have the expected headers
            expected_headers = [
                'id',
                'instrument_id',
                'instrument_name',
                'status',
                'status_display',
                'serial_number',
                'member_id',
                'member_name',
                'rental_date',
                'acquisition_cost',
                'current_value',
                'replacement_cost',
                'patreon_active',
                'patreon_amount',
                'storage_location_id',
                'storage_location_name',
                'comments',
                'created_at',
                'updated_at',
            ]
            self.assertEqual(headers, expected_headers)

    def test_export_library_instruments_csv_format(self):
        """Test that the CSV has proper format and required columns."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as tmp:
            tmp_path = tmp.name

        try:
            call_command('export_library_instruments_to_csv', output_path=tmp_path, stdout=StringIO())

            with open(tmp_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                headers = reader.fieldnames
                
                # Verify all required headers are present
                required_headers = [
                    'id',
                    'instrument_id',
                    'instrument_name',
                    'status',
                    'status_display',
                    'serial_number',
                    'member_id',
                    'member_name',
                    'rental_date',
                    'acquisition_cost',
                    'current_value',
                    'replacement_cost',
                    'patreon_active',
                    'patreon_amount',
                    'storage_location_id',
                    'storage_location_name',
                    'comments',
                    'created_at',
                    'updated_at',
                ]

                for header in required_headers:
                    self.assertIn(header, headers)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
