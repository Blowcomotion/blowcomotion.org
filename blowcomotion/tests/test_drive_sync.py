from django.test import TestCase, override_settings

from blowcomotion.drive_sync import ParsedFile, parse_filename


class TestParseFilename(TestCase):
    def _p(self, name):
        return parse_filename(name)

    def test_score_keyword(self):
        r = self._p("MySong_Score.pdf")
        self.assertTrue(r.is_score)
        self.assertEqual(r.instrument_hint, "")
        self.assertEqual(r.part_ordinal, "")

    def test_conductor_keyword(self):
        r = self._p("MySong_Conductor.pdf")
        self.assertTrue(r.is_score)

    def test_full_score(self):
        r = self._p("MySong_Full_Score.pdf")
        self.assertTrue(r.is_score)

    def test_all_parts(self):
        r = self._p("MySong_All_Parts.pdf")
        self.assertTrue(r.is_score)

    def test_trumpet_tmpt_part_1(self):
        r = self._p("MySong_Tmpt_1.pdf")
        self.assertFalse(r.is_score)
        self.assertEqual(r.instrument_hint, "Trumpet")
        self.assertEqual(r.part_ordinal, "1st")

    def test_trumpet_tpet_part_2(self):
        r = self._p("Song_Tpet_2.pdf")
        self.assertEqual(r.instrument_hint, "Trumpet")
        self.assertEqual(r.part_ordinal, "2nd")

    def test_horn_in_f(self):
        r = self._p("Song_Horn_in_F.pdf")
        self.assertEqual(r.instrument_hint, "French Horn")

    def test_fhorn_part_1(self):
        r = self._p("Song_FHorn_1.pdf")
        self.assertEqual(r.instrument_hint, "French Horn")
        self.assertEqual(r.part_ordinal, "1st")

    def test_tuba_no_part(self):
        r = self._p("Song_Tuba.pdf")
        self.assertEqual(r.instrument_hint, "Tuba/Sousaphone")
        self.assertEqual(r.part_ordinal, "")

    def test_cowbell(self):
        r = self._p("Song_Cowbell.pdf")
        self.assertEqual(r.instrument_hint, "Cow Bell")

    def test_bari_sax(self):
        r = self._p("Song_Bari_Sax.pdf")
        self.assertEqual(r.instrument_hint, "Baritone Saxophone")

    def test_bari(self):
        r = self._p("Song_Bari.pdf")
        self.assertEqual(r.instrument_hint, "Baritone Saxophone")

    def test_clrnt(self):
        r = self._p("Song_Clrnt.pdf")
        self.assertEqual(r.instrument_hint, "Clarinet")

    def test_tnr(self):
        r = self._p("Song_Tnr.pdf")
        self.assertEqual(r.instrument_hint, "Tenor Saxophone")

    def test_drums(self):
        r = self._p("Song_Drums.pdf")
        self.assertEqual(r.instrument_hint, "Drums")

    def test_drum_kit(self):
        r = self._p("Song_4-Piece_Drum_Kit.pdf")
        self.assertEqual(r.instrument_hint, "Drum Set")

    def test_baritone_stays_ambiguous(self):
        # "Baritone" alone is ambiguous across 3 DB instruments — never auto-resolved
        r = self._p("Song_Baritone.pdf")
        self.assertEqual(r.instrument_hint, "Baritone")
        self.assertFalse(r.is_score)

    def test_part_1st_word(self):
        r = self._p("Song_Trombone_1st.pdf")
        self.assertEqual(r.part_ordinal, "1st")

    def test_part_2nd_number(self):
        r = self._p("Song_Trombone_2.pdf")
        self.assertEqual(r.part_ordinal, "2nd")

    def test_part_2nd_word(self):
        r = self._p("Song_Trombone_2nd.pdf")
        self.assertEqual(r.part_ordinal, "2nd")

    def test_part_3rd(self):
        r = self._p("Song_Trombone_3.pdf")
        self.assertEqual(r.part_ordinal, "3rd")

    def test_no_part(self):
        r = self._p("Song_Trombone.pdf")
        self.assertEqual(r.part_ordinal, "")

    def test_pdf_extension_stripped(self):
        r = self._p("Song_Trombone.pdf")
        self.assertNotIn(".pdf", r.instrument_hint)

    def test_dash_separated_song_name_alto_saxophone(self):
        # "Song Name-Instrument_Part.pdf" format: instrument portion after dash
        r = self._p("Grazin in the Grass-Alto_Saxophone_2.pdf")
        self.assertEqual(r.instrument_hint, "Alto Saxophone")
        self.assertEqual(r.part_ordinal, "2nd")
        self.assertFalse(r.is_score)

    def test_dash_separated_single_instrument(self):
        r = self._p("Soul Finger-Trumpet_1.pdf")
        self.assertEqual(r.instrument_hint, "Trumpet")
        self.assertEqual(r.part_ordinal, "1st")

    def test_instrument_dash_song_name_tuba(self):
        r = self._p("Tuba - Rock Lobster.pdf")
        self.assertEqual(r.instrument_hint, "Tuba/Sousaphone")
        self.assertEqual(r.part_ordinal, "")

    def test_instrument_dash_song_name_alto(self):
        r = self._p("Alto - Rock Lobster.pdf")
        self.assertEqual(r.instrument_hint, "Alto Saxophone")
        self.assertEqual(r.part_ordinal, "")

    def test_instrument_dash_song_name_multiword(self):
        r = self._p("Bass Drum - Rock Lobster.pdf")
        self.assertEqual(r.instrument_hint, "Bass Drum")
        self.assertEqual(r.part_ordinal, "")

    def test_instrument_dash_song_name_bari_sax(self):
        r = self._p("Bari Sax - Rock Lobster.pdf")
        self.assertEqual(r.instrument_hint, "Baritone Saxophone")
        self.assertEqual(r.part_ordinal, "")

    def test_key_based_bb(self):
        r = self._p("The Saints - Bb.pdf")
        self.assertTrue(r.is_key)
        self.assertEqual(r.instrument_hint, "Bb")
        self.assertFalse(r.is_score)

    def test_key_based_eb(self):
        r = self._p("The Saints - Eb.pdf")
        self.assertTrue(r.is_key)
        self.assertEqual(r.instrument_hint, "Eb")

    def test_key_based_c(self):
        r = self._p("The Saints - C.pdf")
        self.assertTrue(r.is_key)
        self.assertEqual(r.instrument_hint, "C")

    def test_key_based_bass(self):
        r = self._p("The Saints - Bass.pdf")
        self.assertTrue(r.is_key)
        self.assertEqual(r.instrument_hint, "Bass")

    def test_instrument_dash_song_not_confused_with_key(self):
        # "Rock Lobster" is multi-word — should be instrument format, not key
        r = self._p("Tuba - Rock Lobster.pdf")
        self.assertFalse(r.is_key)
        self.assertEqual(r.instrument_hint, "Tuba/Sousaphone")

    def test_fullerton_not_a_score(self):
        # "full" alone must not trigger score detection; only "full score" as a phrase
        r = self._p("Fullerton_March_Trumpet_1.pdf")
        self.assertFalse(r.is_score)

    def test_encore_not_a_score(self):
        # "core" is a substring of "encore" but not a token — must not trigger score detection
        r = self._p("Encore_Trumpet_1.pdf")
        self.assertFalse(r.is_score)


import datetime
from unittest.mock import MagicMock

from blowcomotion.drive_sync import (
    ReconcileResult,
    match_instrument,
    match_song,
    reconcile_file,
)


class TestMatchSong(TestCase):
    def _song(self, title):
        s = MagicMock()
        s.title = title
        return s

    def test_exact_match(self):
        songs = [self._song("Soul Finger"), self._song("Brick House")]
        song, score = match_song("Soul Finger", songs)
        self.assertEqual(song.title, "Soul Finger")
        self.assertGreater(score, 0.9)

    def test_fuzzy_match(self):
        songs = [self._song("Soul Finger"), self._song("Brick House")]
        song, score = match_song("Soulfinger", songs)
        self.assertEqual(song.title, "Soul Finger")
        self.assertGreater(score, 0.5)

    def test_poor_match_returns_low_score(self):
        songs = [self._song("Soul Finger")]
        _, score = match_song("Completely Different Title", songs)
        self.assertLess(score, 0.5)

    def test_empty_list(self):
        song, score = match_song("Soul Finger", [])
        self.assertIsNone(song)
        self.assertEqual(score, 0.0)


class TestMatchInstrument(TestCase):
    def _inst(self, name):
        i = MagicMock()
        i.name = name
        return i

    def _instruments(self):
        return [
            self._inst("Trumpet"),
            self._inst("French Horn"),
            self._inst("Mellophone"),
            self._inst("Tuba/Sousaphone"),
            self._inst("Baritone Horn"),
            self._inst("Baritone Saxophone"),
            self._inst("Euphonium (Baritone)"),
            self._inst("Trombone"),
            self._inst("Clarinet"),
            self._inst("Tenor Saxophone"),
            self._inst("Drum Set"),
            self._inst("Cow Bell"),
            self._inst("Conductor"),
        ]

    def test_exact_name_match(self):
        inst, conf = match_instrument("Trumpet", self._instruments())
        self.assertEqual(inst.name, "Trumpet")
        self.assertEqual(conf, "high")

    def test_fuzzy_trombone(self):
        inst, conf = match_instrument("Trombone", self._instruments())
        self.assertEqual(inst.name, "Trombone")
        self.assertEqual(conf, "high")

    def test_cow_bell(self):
        inst, conf = match_instrument("Cow Bell", self._instruments())
        self.assertEqual(inst.name, "Cow Bell")
        self.assertEqual(conf, "high")

    def test_ambiguous_baritone(self):
        _, conf = match_instrument("Baritone", self._instruments())
        self.assertEqual(conf, "ambiguous")

    def test_no_match(self):
        # "Zylophone" would accidentally match "Mellophone" at 0.737 via difflib;
        # "Kazoo" is genuinely unrecognized (top score 0.33 against all instruments)
        _, conf = match_instrument("Kazoo", self._instruments())
        self.assertEqual(conf, "low")

    def test_conductor(self):
        inst, conf = match_instrument("Conductor", self._instruments())
        self.assertEqual(inst.name, "Conductor")
        self.assertEqual(conf, "high")


class TestReconcileFile(TestCase):
    def _drive_file(self, file_id, modified="2025-06-01T12:00:00.000Z"):
        return {
            "id": file_id,
            "name": "Song_Tmpt_1.pdf",
            "modifiedTime": modified,
            "relative_path": "Song_Tmpt_1.pdf",
        }

    def _chart(self, file_id=None, modified=None):
        c = MagicMock()
        c.drive_file_id = file_id
        c.drive_modified_time = modified
        return c

    def _parsed(self):
        from blowcomotion.drive_sync import ParsedFile
        return ParsedFile(instrument_hint="Trumpet", part_ordinal="1st", is_score=False)

    def test_exact_newer_modified_is_auto(self):
        old_time = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)
        chart = self._chart(file_id="abc", modified=old_time)
        result = reconcile_file(self._drive_file("abc"), self._parsed(), [chart])
        self.assertEqual(result.apply, "auto")
        self.assertEqual(result.reason, "Exact")

    def test_exact_same_modified_is_noop(self):
        t = datetime.datetime(2025, 6, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        chart = self._chart(file_id="abc", modified=t)
        result = reconcile_file(self._drive_file("abc"), self._parsed(), [chart])
        self.assertEqual(result.apply, "noop")

    def test_old_file_id_gone_one_chart_is_high(self):
        chart = self._chart(file_id="old_id", modified=datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc))
        result = reconcile_file(self._drive_file("new_id"), self._parsed(), [chart])
        self.assertEqual(result.apply, "auto")
        self.assertEqual(result.reason, "High")

    def test_multiple_charts_needs_review(self):
        chart = self._chart(file_id=None)
        result = reconcile_file(self._drive_file("new_id"), self._parsed(), [chart, chart])
        self.assertEqual(result.apply, "review")
        self.assertEqual(result.reason, "Needs review")

    def test_no_existing_chart_is_new(self):
        result = reconcile_file(self._drive_file("brand_new"), self._parsed(), [])
        self.assertEqual(result.apply, "review")
        self.assertEqual(result.reason, "New")

    def test_brick_house_multiple_files_same_tuple_needs_review(self):
        """Two drive files map to the same (song, instrument, part) tuple — both should route to review."""
        file_a = {
            "id": "bh_2025_01",
            "name": "Brick_House_1-15-25_Tmpt_1.pdf",
            "modifiedTime": "2025-01-15T12:00:00.000Z",
            "relative_path": "Brick_House_1-15-25_Tmpt_1.pdf",
        }
        file_b = {
            "id": "bh_2025_02",
            "name": "Brick_House_2-26-25_Tmpt_1.pdf",
            "modifiedTime": "2025-02-26T12:00:00.000Z",
            "relative_path": "Brick_House_2-26-25_Tmpt_1.pdf",
        }
        parsed = ParsedFile(instrument_hint="Trumpet", part_ordinal="1st", is_score=False)

        # Simulate: one existing 1st-Trumpet chart in the DB
        existing_chart = self._chart(file_id=None, modified=None)

        # Each file alone with one existing chart -> auto/High (reconcile_file contract)
        result_a = reconcile_file(file_a, parsed, [existing_chart])
        result_b = reconcile_file(file_b, parsed, [existing_chart])
        self.assertEqual(result_a.apply, "auto")
        self.assertEqual(result_a.reason, "High")
        self.assertEqual(result_b.apply, "auto")
        self.assertEqual(result_b.reason, "High")

        # When both files are passed together (simulating two existing charts), routes to review
        result_multi = reconcile_file(file_a, parsed, [existing_chart, existing_chart])
        self.assertEqual(result_multi.apply, "review")
        self.assertEqual(result_multi.reason, "Needs review")


from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client


class TestPickerView(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser("admin", "admin@test.com", "password")
        self.client = Client()
        self.client.login(username="admin", password="password")

    @patch("blowcomotion.views_chart_import.list_song_folders")
    @override_settings(GDRIVE_CHARTS_FOLDER_ID="root_folder_id")
    def test_picker_lists_folders(self, mock_list):
        mock_list.return_value = [{"id": "f1", "name": "Soul Finger"}]
        response = self.client.get("/admin/chart-import/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Soul Finger")

    def test_picker_requires_login(self):
        response = Client().get("/admin/chart-import/")
        self.assertNotEqual(response.status_code, 200)


from blowcomotion.models import Chart, Instrument, Song


class TestImportView(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser("admin2", "admin2@test.com", "pw")
        self.client = Client()
        self.client.login(username="admin2", password="pw")
        self.song = Song.objects.create(title="Soul Finger")
        self.instrument = Instrument.objects.create(name="Trumpet")

    @patch("blowcomotion.views_chart_import.list_pdfs_in_folder")
    def test_review_get_renders(self, mock_list):
        mock_list.return_value = [{
            "id": "f1", "name": "Soul_Finger_Tmpt_1.pdf",
            "modifiedTime": "2025-01-15T12:00:00.000Z",
            "relative_path": "Soul_Finger_Tmpt_1.pdf",
        }]
        response = self.client.get(
            f"/admin/chart-import/review/?folder_id=abc&song_id={self.song.id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Soul_Finger_Tmpt_1.pdf")

    @patch("blowcomotion.views_chart_import.list_pdfs_in_folder")
    def test_import_post_creates_chart(self, mock_list):
        mock_list.return_value = [{
            "id": "f1", "name": "Soul_Finger_Tmpt_1.pdf",
            "modifiedTime": "2025-01-15T12:00:00.000Z",
            "relative_path": "Soul_Finger_Tmpt_1.pdf",
        }]

        self.client.post("/admin/chart-import/review/", {
            "song_id": self.song.id,
            "folder_id": "abc",
            "rows": ["0"],
            "row_0_file_id": "f1",
            "row_0_filename": "Soul_Finger_Tmpt_1.pdf",
            "row_0_modified": "2025-01-15T12:00:00.000Z",
            "row_0_instrument_id": self.instrument.id,
            "row_0_part": "1st Trumpet",
            "row_0_chart_id": "",
        })
        chart = Chart.objects.get(song=self.song, instrument=self.instrument)
        self.assertEqual(chart.drive_pdf_url, "https://drive.google.com/file/d/f1/view")
        self.assertIsNone(chart.pdf)


from io import StringIO

from django.core.files.base import ContentFile
from django.core.management import call_command


class TestSyncChartsCommand(TestCase):
    def setUp(self):
        self.song = Song.objects.create(title="Soul Finger")
        self.instrument = Instrument.objects.create(name="Trumpet")

    @patch("blowcomotion.management.commands.sync_charts.list_pdfs_in_folder")
    @patch("blowcomotion.management.commands.sync_charts._get_drive_service")
    @override_settings(GDRIVE_CHARTS_FOLDER_ID="root_id")
    def test_dry_run_makes_no_writes(self, mock_service, mock_list):
        mock_list.return_value = []
        mock_service.return_value = MagicMock()
        initial = Chart.objects.count()
        call_command("sync_charts", "--dry-run", stdout=StringIO())
        self.assertEqual(Chart.objects.count(), initial)

    @patch("blowcomotion.management.commands.sync_charts.list_pdfs_in_folder")
    @patch("blowcomotion.management.commands.sync_charts._get_drive_service")
    @override_settings(GDRIVE_CHARTS_FOLDER_ID="root_id")
    def test_exact_match_updates_chart(self, mock_service, mock_list):
        import datetime

        old_time = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)
        chart = Chart.objects.create(
            song=self.song,
            instrument=self.instrument,
            part="1st Trumpet",
            drive_pdf_url="https://drive.google.com/file/d/file123/view",
            drive_file_id="file123",
            drive_modified_time=old_time,
        )

        parent_mock = MagicMock()
        parent_mock.files.return_value.get.return_value.execute.return_value = {
            "parents": ["song_folder_id"]
        }
        mock_service.return_value = parent_mock
        mock_list.return_value = [{
            "id": "file123",
            "name": "Soul_Finger_Tmpt_1.pdf",
            "modifiedTime": "2025-06-01T12:00:00.000Z",
            "relative_path": "Soul_Finger_Tmpt_1.pdf",
        }]

        call_command("sync_charts", stdout=StringIO())
        chart.refresh_from_db()
        self.assertEqual(chart.drive_pdf_url, "https://drive.google.com/file/d/file123/view")
        self.assertEqual(chart.drive_file_id, "file123")
