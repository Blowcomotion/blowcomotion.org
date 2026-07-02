"""
Tests for the export_members_to_csv management command.
"""
import csv
import datetime
import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from blowcomotion.models import Instrument, Member, MemberInstrument

# Columns added to the Member model since 6/01/26 that must always be present
# in the export. If a new column is added to Member, add it here too so a
# regression that drops it from the CSV fails this test.
RECENTLY_ADDED_MEMBER_COLUMNS = [
    "reactivated_date",
    "inspired_by",
    "shirt_size",
    "dietary_preferences",
    "dietary_other",
    "has_allergies",
    "allergens",
    "allergens_other",
    "has_epipen",
    "allergy_details",
    "medical_notes",
    "user_id",
    "pending_email",
    "notify_rental_updates",
    "notify_reminders",
    "notify_announcements",
    "patreon_is_active",
    "patreon_pledge_cents",
    "patreon_last_charge_date",
    "patreon_last_charge_status",
    "patreon_patron_since",
    "patreon_lifetime_cents",
    "patreon_last_synced",
]


class ExportMembersToCSVCommandTest(TestCase):
    """Tests for the export_members_to_csv management command."""

    def setUp(self):
        self.trumpet = Instrument.objects.create(name="Trumpet")
        self.trombone = Instrument.objects.create(name="Trombone")

        self.member = Member.objects.create(
            first_name="Ada",
            last_name="Lovelace",
            primary_instrument=self.trumpet,
            shirt_size="M",
            dietary_preferences=["Vegan", "Gluten-Free"],
            has_allergies=True,
            allergens=["Peanuts"],
            has_epipen=True,
            allergy_details="Carries an Epi-Pen at all times.",
            medical_notes="No other concerns.",
            inspired_by="A friend in the band.",
            reactivated_date=datetime.date(2026, 6, 15),
            patreon_is_active=True,
            patreon_pledge_cents=500,
        )
        MemberInstrument.objects.create(member=self.member, instrument=self.trombone)

    def test_csv_includes_every_concrete_member_field(self):
        """The exported header must always match every concrete field on Member."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as tmp:
            tmp_path = tmp.name

        try:
            call_command(
                "export_members_to_csv",
                output_path=tmp_path,
                include_extra=True,
                stdout=StringIO(),
            )

            with open(tmp_path, "r", encoding="utf-8") as csvfile:
                headers = next(csv.reader(csvfile))

            expected_field_names = [
                field.attname for field in Member._meta.concrete_fields
            ]
            for field_name in expected_field_names:
                self.assertIn(field_name, headers)

            for column in RECENTLY_ADDED_MEMBER_COLUMNS:
                self.assertIn(column, headers)

            self.assertIn("primary_instrument_name", headers)
            self.assertIn("additional_instruments", headers)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_recently_added_field_values_are_exported(self):
        """Values for the recently-added categories should round-trip into the CSV row."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as tmp:
            tmp_path = tmp.name

        try:
            call_command(
                "export_members_to_csv",
                output_path=tmp_path,
                include_extra=True,
                stdout=StringIO(),
            )

            with open(tmp_path, "r", encoding="utf-8") as csvfile:
                rows = list(csv.DictReader(csvfile))

            self.assertEqual(len(rows), 1)
            row = rows[0]

            self.assertEqual(row["shirt_size"], "M")
            self.assertEqual(row["dietary_preferences"], "Vegan; Gluten-Free")
            self.assertEqual(row["has_allergies"], "YES")
            self.assertEqual(row["allergens"], "Peanuts")
            self.assertEqual(row["has_epipen"], "YES")
            self.assertEqual(row["allergy_details"], "Carries an Epi-Pen at all times.")
            self.assertEqual(row["medical_notes"], "No other concerns.")
            self.assertEqual(row["inspired_by"], "A friend in the band.")
            self.assertEqual(row["reactivated_date"], "2026-06-15")
            self.assertEqual(row["patreon_is_active"], "YES")
            self.assertEqual(row["patreon_pledge_cents"], "500")
            self.assertEqual(row["primary_instrument_name"], "Trumpet")
            self.assertEqual(row["additional_instruments"], "Trombone")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
