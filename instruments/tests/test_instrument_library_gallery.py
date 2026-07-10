"""
Unit tests for the Instrument Gallery admin dashboard view.
"""
from wagtail.images import get_image_model
from wagtail.images.tests.utils import get_test_image_file

from django.contrib.auth.models import ContentType, Permission, User
from django.test import Client, TestCase
from django.urls import reverse

from blowcomotion.models import Instrument, LibraryInstrument, LibraryInstrumentPhoto

Image = get_image_model()


def make_instrument(name="Trumpet"):
    return Instrument.objects.create(name=name)


def make_library_instrument(instrument, status=LibraryInstrument.STATUS_AVAILABLE, serial="SN001"):
    return LibraryInstrument.objects.create(
        instrument=instrument, serial_number=serial, status=status
    )


class InstrumentLibraryGalleryTests(TestCase):
    def setUp(self):
        self.client = Client()
        ct = ContentType.objects.get_for_model(LibraryInstrument)
        self.change_perm = Permission.objects.get(content_type=ct, codename='change_libraryinstrument')
        self.access_admin_perm = Permission.objects.get(
            content_type__app_label='wagtailadmin', codename='access_admin'
        )
        self.librarian = User.objects.create_user(username='librarian', password='pw', is_staff=True)
        self.librarian.user_permissions.add(self.change_perm, self.access_admin_perm)

    def test_staff_without_permission_denied(self):
        user = User.objects.create_user(username='staff', password='pw', is_staff=True)
        user.user_permissions.add(self.access_admin_perm)
        self.client.login(username='staff', password='pw')
        response = self.client.get(reverse('instrument_library_gallery'))
        self.assertRedirects(
            response, reverse('wagtailadmin_home'), fetch_redirect_response=False
        )

    def test_library_manager_sees_instrument_and_photo(self):
        instrument = make_instrument()
        li = make_library_instrument(instrument, serial="SN12345")
        image = Image.objects.create(title="Trumpet photo", file=get_test_image_file())
        LibraryInstrumentPhoto.objects.create(library_instrument=li, image=image)

        self.client.login(username='librarian', password='pw')
        response = self.client.get(reverse('instrument_library_gallery'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SN12345")
        self.assertNotContains(response, "No photo")

    def test_create_new_button_requires_add_permission(self):
        self.client.login(username='librarian', password='pw')
        response = self.client.get(reverse('instrument_library_gallery'))
        self.assertNotContains(response, "Create New")

        ct = ContentType.objects.get_for_model(LibraryInstrument)
        add_perm = Permission.objects.get(content_type=ct, codename='add_libraryinstrument')
        self.librarian.user_permissions.add(add_perm)
        response = self.client.get(reverse('instrument_library_gallery'))
        self.assertContains(response, "Create New")
        self.assertContains(response, reverse('wagtailsnippets_blowcomotion_libraryinstrument:add'))

    def test_no_photo_placeholder(self):
        instrument = make_instrument()
        make_library_instrument(instrument, serial="SN99999")

        self.client.login(username='librarian', password='pw')
        response = self.client.get(reverse('instrument_library_gallery'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No photo")

    def test_status_filter_narrows_results(self):
        instrument = make_instrument()
        make_library_instrument(instrument, status=LibraryInstrument.STATUS_AVAILABLE, serial="AVAIL001")
        make_library_instrument(instrument, status=LibraryInstrument.STATUS_NEEDS_REPAIR, serial="REPAIR001")

        self.client.login(username='librarian', password='pw')
        response = self.client.get(
            reverse('instrument_library_gallery'), {'status': LibraryInstrument.STATUS_NEEDS_REPAIR}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "REPAIR001")
        self.assertNotContains(response, "AVAIL001")

    def test_pagination_page_two(self):
        instrument = make_instrument()
        LibraryInstrument.objects.bulk_create([
            LibraryInstrument(
                instrument=instrument,
                serial_number=f"SN{i:03d}",
                status=LibraryInstrument.STATUS_AVAILABLE,
            )
            for i in range(25)
        ])

        self.client.login(username='librarian', password='pw')
        response = self.client.get(reverse('instrument_library_gallery'), {'page': 2})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Page 2 of 2")

    def test_bad_page_number_does_not_500(self):
        instrument = make_instrument()
        make_library_instrument(instrument, serial="SN00001")

        self.client.login(username='librarian', password='pw')
        response = self.client.get(reverse('instrument_library_gallery'), {'page': 'not-a-number'})
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('instrument_library_gallery'), {'page': 999})
        self.assertEqual(response.status_code, 200)

    def test_bad_fk_filter_params_do_not_500(self):
        instrument = make_instrument()
        make_library_instrument(instrument, serial="SN00001")

        self.client.login(username='librarian', password='pw')
        response = self.client.get(
            reverse('instrument_library_gallery'), {'instrument': 'abc', 'storage_location': 'xyz'}
        )
        self.assertEqual(response.status_code, 200)

    def test_query_filter_matches_serial_and_preserves_filters_on_page_two(self):
        instrument = make_instrument()
        other_instrument = make_instrument(name="Trombone")
        LibraryInstrument.objects.bulk_create([
            LibraryInstrument(
                instrument=instrument,
                serial_number=f"MATCH{i:03d}",
                status=LibraryInstrument.STATUS_AVAILABLE,
            )
            for i in range(25)
        ])
        make_library_instrument(other_instrument, status=LibraryInstrument.STATUS_AVAILABLE, serial="OTHER001")

        self.client.login(username='librarian', password='pw')
        response = self.client.get(
            reverse('instrument_library_gallery'), {'q': 'MATCH', 'page': 2}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Page 2 of 2")
        self.assertNotContains(response, "OTHER001")
        # the filter must be preserved in the pagination links on page 2
        self.assertContains(response, "q=MATCH")
