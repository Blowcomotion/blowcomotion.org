from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from blowcomotion.models import (
    AttendanceRecord,
    CachedGig,
    Chart,
    CustomImage,
    Equipment,
    Event,
    InstrumentHistoryLog,
    InstrumentStorageLocation,
    LibraryInstrument,
    Song,
    SongConductor,
    SongSoloist,
    SongVideo,
)


def _model_perms(model, actions=("add", "change", "delete", "view")):
    ct = ContentType.objects.get_for_model(model)
    codenames = [f"{action}_{model._meta.model_name}" for action in actions]
    return list(Permission.objects.filter(content_type=ct, codename__in=codenames))


def _named_perm(app_label, codename):
    return list(Permission.objects.filter(content_type__app_label=app_label, codename=codename))


ACCESS_ADMIN = lambda: _named_perm("wagtailadmin", "access_admin")

ROLE_PERMISSIONS = {
    "Dev": lambda: (
        _named_perm("blowcomotion", "access_dev_tools")
        + _model_perms(CachedGig)
        + ACCESS_ADMIN()
    ),
    "Data Analyst": lambda: (
        _named_perm("blowcomotion", "access_real_data_exports") + ACCESS_ADMIN()
    ),
    "Gig Booker": lambda: _model_perms(CachedGig) + _model_perms(Event) + ACCESS_ADMIN(),
    "Library Manager": lambda: (
        _model_perms(LibraryInstrument)
        + _model_perms(InstrumentHistoryLog)
        + _model_perms(InstrumentStorageLocation)
        + _model_perms(Equipment)
        + ACCESS_ADMIN()
    ),
    "Arranger/Composer": lambda: (
        _model_perms(Chart)
        + _model_perms(Song)
        + _model_perms(SongConductor)
        + _model_perms(SongSoloist)
        + _model_perms(SongVideo)
        + ACCESS_ADMIN()
    ),
    # Attendance Taker's permission set (AttendanceRecord view/add/change) lands
    # with the attendance/birthday login-conversion follow-up plan; created here
    # so the group exists and can be assigned to users ahead of that work.
    "Attendance Taker": lambda: [],
}

EDITOR_GROUP_NAMES = ("Editors", "Moderators")


class Command(BaseCommand):
    help = "Create/update role Groups with their permission sets (safe to re-run)"

    def handle(self, *args, **options):
        for name, get_perms in ROLE_PERMISSIONS.items():
            group, created = Group.objects.get_or_create(name=name)
            group.permissions.set(get_perms())
            self.stdout.write(
                f"{'Created' if created else 'Updated'} group '{name}' "
                f"({group.permissions.count()} perms)"
            )

        self._patch_editor_groups()

    def _patch_editor_groups(self):
        image_perms = _model_perms(CustomImage)
        media_ct = ContentType.objects.filter(app_label="wagtailmedia", model="media").first()
        media_perms = list(Permission.objects.filter(content_type=media_ct)) if media_ct else []
        if not media_perms:
            self.stdout.write(self.style.WARNING("wagtailmedia.Media content type not found, skipping media perms"))

        for group_name in EDITOR_GROUP_NAMES:
            try:
                group = Group.objects.get(name=group_name)
            except Group.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Group '{group_name}' not found, skipping"))
                continue
            group.permissions.add(*image_perms, *media_perms)
            self.stdout.write(f"Patched '{group_name}' with CustomImage + Media permissions")
