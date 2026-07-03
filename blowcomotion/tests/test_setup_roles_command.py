"""
Unit tests for the setup_roles management command.
"""
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
            self.assertIn('change_customimage', codenames)

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
            self.assertIn('change_customimage', codenames)
