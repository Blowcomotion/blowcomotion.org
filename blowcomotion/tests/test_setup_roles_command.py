"""
Unit tests for the setup_roles management command.
"""
from wagtail.models import GroupCollectionPermission, GroupPagePermission, Page

from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import TestCase


class SetupRolesCommandTests(TestCase):
    def _perm_codenames(self, group_name):
        group = Group.objects.get(name=group_name)
        return set(group.permissions.values_list('codename', flat=True))

    def test_creates_dev_group(self):
        call_command('setup_roles')
        codenames = self._perm_codenames('Dev')
        self.assertIn('access_dev_tools', codenames)
        self.assertIn('change_cachedgig', codenames)
        self.assertIn('access_admin', codenames)
        self.assertNotIn('access_real_data_exports', codenames)

    def test_creates_data_analyst_group(self):
        call_command('setup_roles')
        codenames = self._perm_codenames('Data Analyst')
        self.assertIn('access_real_data_exports', codenames)
        self.assertIn('access_admin', codenames)

    def test_creates_gig_booker_group(self):
        call_command('setup_roles')
        codenames = self._perm_codenames('Gig Booker')
        self.assertIn('change_cachedgig', codenames)
        self.assertIn('add_event', codenames)
        self.assertIn('access_admin', codenames)

    def test_creates_library_manager_group(self):
        call_command('setup_roles')
        codenames = self._perm_codenames('Library Manager')
        for expected in ('change_libraryinstrument', 'change_instrumenthistorylog',
                          'change_instrumentstoragelocation', 'change_equipment'):
            self.assertIn(expected, codenames)

    def test_creates_arranger_composer_group(self):
        call_command('setup_roles')
        codenames = self._perm_codenames('Arranger/Composer')
        for expected in ('change_chart', 'change_song', 'change_songconductor',
                          'change_songsoloist', 'change_songvideo'):
            self.assertIn(expected, codenames)

    def test_creates_attendance_taker_group(self):
        call_command('setup_roles')
        codenames = self._perm_codenames('Attendance Taker')
        self.assertIn('view_attendancerecord', codenames)
        self.assertIn('add_attendancerecord', codenames)
        self.assertIn('change_attendancerecord', codenames)
        self.assertIn('access_admin', codenames)

    def test_patches_editors_group_with_image_and_media_perms(self):
        # Wagtail's own migrations already seed "Editors"/"Moderators" groups
        # in a fresh test database, so use get_or_create rather than create
        # to avoid colliding with the unique constraint on Group.name.
        Group.objects.get_or_create(name='Editors')
        Group.objects.get_or_create(name='Moderators')
        call_command('setup_roles')
        for group_name in ('Editors', 'Moderators'):
            codenames = self._perm_codenames(group_name)
            # Permissions are granted against wagtailimages.Image (not the
            # swapped-in CustomImage) since that's what Wagtail's image
            # permission policy actually checks, regardless of which model
            # WAGTAILIMAGES_IMAGE_MODEL points to.
            self.assertIn('change_image', codenames)
            self.assertIn('change_media', codenames)
            self.assertIn('change_notificationbanner', codenames)
            self.assertIn('change_seosettings', codenames)
            self.assertIn('change_collection', codenames)

    def test_grants_page_and_collection_permissions_by_tier(self):
        Group.objects.get_or_create(name='Site Editors')
        Group.objects.get_or_create(name='Site Moderators')
        call_command('setup_roles')

        editors = Group.objects.get(name='Site Editors')
        editor_page_codenames = set(
            GroupPagePermission.objects.filter(group=editors).values_list('permission__codename', flat=True)
        )
        self.assertIn('add_page', editor_page_codenames)
        self.assertIn('change_page', editor_page_codenames)
        self.assertNotIn('publish_page', editor_page_codenames)
        self.assertNotIn('delete_page', editor_page_codenames)

        editor_collection_codenames = set(
            GroupCollectionPermission.objects.filter(group=editors).values_list('permission__codename', flat=True)
        )
        self.assertIn('choose_image', editor_collection_codenames)
        self.assertIn('choose_document', editor_collection_codenames)
        self.assertNotIn('delete_image', editor_collection_codenames)

        moderators = Group.objects.get(name='Site Moderators')
        moderator_page_codenames = set(
            GroupPagePermission.objects.filter(group=moderators).values_list('permission__codename', flat=True)
        )
        self.assertIn('publish_page', moderator_page_codenames)
        self.assertIn('delete_page', moderator_page_codenames)

        moderator_collection_codenames = set(
            GroupCollectionPermission.objects.filter(group=moderators).values_list('permission__codename', flat=True)
        )
        self.assertIn('delete_image', moderator_collection_codenames)

    def test_grants_wiki_editors_page_permissions_scoped_to_wiki_page(self):
        site_root = Page.objects.get(depth=2)
        wiki_page = site_root.add_child(instance=Page(title='Blowco Wiki', slug='wiki'))
        Group.objects.get_or_create(name='Wiki Editors')

        call_command('setup_roles')

        wiki_editors = Group.objects.get(name='Wiki Editors')
        page_perms = GroupPagePermission.objects.filter(group=wiki_editors)
        self.assertTrue(page_perms.exists())
        for perm in page_perms:
            self.assertEqual(perm.page_id, wiki_page.id)

    def test_missing_editors_group_does_not_raise(self):
        Group.objects.filter(name__in=['Editors', 'Moderators']).delete()
        call_command('setup_roles')  # should not raise

    def test_idempotent(self):
        call_command('setup_roles')
        first_count = Group.objects.filter(name='Dev').count()
        first_perms = self._perm_codenames('Dev')
        call_command('setup_roles')
        self.assertEqual(Group.objects.filter(name='Dev').count(), first_count)
        self.assertEqual(self._perm_codenames('Dev'), first_perms)

    def test_patches_this_installs_renamed_editor_groups_with_image_and_media_perms(self):
        # This installation renamed Wagtail's stock "Editors"/"Moderators" groups
        # to "Site Editors"/"Site Moderators" and added wiki-scoped "Wiki Editors"/
        # "Wiki Moderators" groups. None of these match the stock names, so they
        # must be patched too, in addition to (not instead of) the stock names.
        renamed_group_names = (
            'Site Editors', 'Site Moderators',
            'Wiki Editors', 'Wiki Moderators',
        )
        for group_name in renamed_group_names:
            Group.objects.get_or_create(name=group_name)
        call_command('setup_roles')
        for group_name in renamed_group_names:
            codenames = self._perm_codenames(group_name)
            self.assertIn('change_image', codenames)
