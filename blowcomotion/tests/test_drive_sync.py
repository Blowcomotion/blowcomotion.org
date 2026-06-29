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
        self.assertEqual(r.instrument_hint, "Tuba")
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
        self.assertEqual(r.instrument_hint, "Drum Set")

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
            self._inst("Tuba"),
            self._inst("Sousaphone"),
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

    @patch("blowcomotion.views_chart_import._download_pdf")
    @patch("blowcomotion.views_chart_import.list_pdfs_in_folder")
    def test_import_post_creates_chart(self, mock_list, mock_dl):
        mock_list.return_value = [{
            "id": "f1", "name": "Soul_Finger_Tmpt_1.pdf",
            "modifiedTime": "2025-01-15T12:00:00.000Z",
            "relative_path": "Soul_Finger_Tmpt_1.pdf",
        }]
        mock_dl.return_value = b"%PDF-1.4 test content"

        response = self.client.post("/admin/chart-import/review/", {
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
        self.assertEqual(Chart.objects.filter(song=self.song, instrument=self.instrument).count(), 1)
