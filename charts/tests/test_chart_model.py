"""
Unit tests for the Chart model's clean() validator.
"""

from wagtail.documents.models import Document

from django.core.exceptions import ValidationError
from django.test import TestCase

from blowcomotion.models import Chart, Instrument, Song


class ChartCleanValidationTests(TestCase):
    def setUp(self):
        self.song = Song.objects.create(title="Test Song")
        self.instrument = Instrument.objects.create(name="Trumpet")
        self.pdf = Document.objects.create(title="Test Chart", file="test.pdf")

    def _chart(self, **kwargs):
        return Chart(song=self.song, instrument=self.instrument, **kwargs)

    def test_clean_raises_when_neither_pdf_nor_url(self):
        chart = self._chart()
        with self.assertRaises(ValidationError):
            chart.clean()

    def test_clean_passes_with_pdf_only(self):
        chart = self._chart(pdf=self.pdf)
        chart.clean()

    def test_clean_passes_with_drive_pdf_url_only(self):
        chart = self._chart(drive_pdf_url="https://drive.google.com/file/d/f1/view")
        chart.clean()

    def test_clean_passes_with_both_pdf_and_drive_pdf_url(self):
        chart = self._chart(
            pdf=self.pdf,
            drive_pdf_url="https://drive.google.com/file/d/f1/view",
        )
        chart.clean()

    def test_clean_raises_when_no_instrument_and_not_conductor(self):
        chart = Chart(song=self.song, drive_pdf_url="https://drive.google.com/file/d/f1/view")
        with self.assertRaises(ValidationError):
            chart.clean()

    def test_clean_passes_conductor_chart_without_instrument(self):
        chart = Chart(
            song=self.song,
            is_conductor_chart=True,
            drive_pdf_url="https://drive.google.com/file/d/f1/view",
        )
        chart.clean()

    def test_clean_raises_conductor_chart_with_instrument(self):
        chart = Chart(
            song=self.song,
            instrument=self.instrument,
            is_conductor_chart=True,
            drive_pdf_url="https://drive.google.com/file/d/f1/view",
        )
        with self.assertRaises(ValidationError):
            chart.clean()

    def test_str_conductor_chart(self):
        chart = Chart(
            song=self.song,
            is_conductor_chart=True,
            drive_pdf_url="https://drive.google.com/file/d/f1/view",
        )
        self.assertEqual(str(chart), "Test Song - Conductor Score")
