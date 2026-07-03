from wagtail.documents import get_document_model
from wagtail.images.models import Image as WagtailImage
from wagtail.models import (
    Collection,
    GroupCollectionPermission,
    GroupPagePermission,
    GroupSitePermission,
    Page,
    Site,
)
from wagtailmedia.models import get_media_model

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from blowcomotion.models import (
    AttendanceRecord,
    CachedGig,
    Chart,
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
    # Grants admin access to the AttendanceRecord snippet UI. The public
    # attendance/birthday views (attendance_capture, birthdays, etc.) still use
    # the separate HTTP Basic Auth password until the #301 follow-up converts
    # them to this permission.
    "Attendance Taker": lambda: _model_perms(AttendanceRecord) + ACCESS_ADMIN(),
}

# tier: "editor" (add/change) or "moderator" (add/change/publish/delete/lock)
# scope: "site" (whole site, from the default Site's root page) or "wiki" (the
#        "Blowco Wiki" page subtree only, looked up by slug)
EDITOR_GROUP_CONFIG = {
    "Editors": ("editor", "site"),                # Wagtail's stock default (fresh installs / test DB)
    "Moderators": ("moderator", "site"),           # Wagtail's stock default (fresh installs / test DB)
    "Site Editors": ("editor", "site"),            # this install's renamed default
    "Site Moderators": ("moderator", "site"),      # this install's renamed default
    "Wiki Editors": ("editor", "wiki"),            # this install's wiki-scoped editor group
    "Wiki Moderators": ("moderator", "wiki"),      # this install's wiki-scoped editor group
}

EDITOR_PAGE_CODENAMES = ("add_page", "change_page")
MODERATOR_PAGE_CODENAMES = (
    "add_page", "change_page", "publish_page", "delete_page", "lock_page", "unlock_page",
)

# Actions per collection-scoped model. Note: Wagtail's image permission policy
# always checks permissions against the base wagtail.images.models.Image model
# (app_label "wagtailimages"), even though WAGTAILIMAGES_IMAGE_MODEL is swapped
# to blowcomotion.CustomImage here - so permissions must be granted against
# Image, not CustomImage, or the chooser silently denies everyone.
# wagtailmedia's Media has no "choose" permission defined in this install (a
# third-party package limitation, not declared in its Meta.permissions), so
# it's omitted rather than granting a Permission row that doesn't exist.
EDITOR_COLLECTION_MODEL_ACTIONS = {
    WagtailImage: ("add", "change", "view", "choose"),
    get_media_model(): ("add", "change", "view"),
    get_document_model(): ("add", "change", "view", "choose"),
    # Wagtail migration 0066 moved collection management from a flat
    # add/change/delete_collection Permission to per-collection
    # GroupCollectionPermission records - granting the flat Permission is a
    # no-op for both the admin UI and the actual permission check.
    Collection: ("add", "change"),
}
MODERATOR_COLLECTION_MODEL_ACTIONS = {
    WagtailImage: ("add", "change", "delete", "view", "choose"),
    get_media_model(): ("add", "change", "delete", "view"),
    get_document_model(): ("add", "change", "delete", "view", "choose"),
    Collection: ("add", "change", "delete"),
}


def _site_root_page():
    site = Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    return site.root_page if site else None


def _grant_page_perms(group, page, codenames):
    ct = ContentType.objects.get_for_model(Page)
    for perm in Permission.objects.filter(content_type=ct, codename__in=codenames):
        GroupPagePermission.objects.get_or_create(group=group, page=page, permission=perm)


def _grant_collection_perms(group, collection, model_actions):
    for model, actions in model_actions.items():
        for perm in _model_perms(model, actions):
            GroupCollectionPermission.objects.get_or_create(group=group, collection=collection, permission=perm)


def _grant_site_setting_perms(group, perms, sites):
    for perm in perms:
        for site in sites:
            GroupSitePermission.objects.get_or_create(group=group, site=site, permission=perm)


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
        image_perms = _model_perms(WagtailImage)
        media_perms = _model_perms(get_media_model())
        # NotificationBanner and SEO settings are Wagtail BaseSiteSetting
        # models - their permission policy checks per-site GroupSitePermission
        # records, not the flat Group.permissions M2M, so these are granted
        # via _grant_site_setting_perms() below rather than group.permissions.add().
        site_setting_perms = (
            _named_perm("blowcomotion", "change_notificationbanner")
            + _named_perm("wagtailseo", "change_seosettings")
        )

        root_collection = Collection.get_first_root_node()
        site_root_page = _site_root_page()
        all_sites = list(Site.objects.all())
        wiki_root_page = Page.objects.filter(slug="wiki").first()
        if wiki_root_page is None:
            self.stdout.write(self.style.WARNING("No page with slug 'wiki' found, skipping Wiki group page permissions"))

        for group_name, (tier, scope) in EDITOR_GROUP_CONFIG.items():
            try:
                group = Group.objects.get(name=group_name)
            except Group.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Group '{group_name}' not found, skipping"))
                continue

            group.permissions.add(*image_perms, *media_perms)
            _grant_site_setting_perms(group, site_setting_perms, all_sites)
            self.stdout.write(f"Patched '{group_name}' with Image + Media + site-settings permissions")

            collection_actions = (
                MODERATOR_COLLECTION_MODEL_ACTIONS if tier == "moderator" else EDITOR_COLLECTION_MODEL_ACTIONS
            )
            _grant_collection_perms(group, root_collection, collection_actions)

            scope_page = wiki_root_page if scope == "wiki" else site_root_page
            if scope_page is not None:
                page_codenames = MODERATOR_PAGE_CODENAMES if tier == "moderator" else EDITOR_PAGE_CODENAMES
                _grant_page_perms(group, scope_page, page_codenames)

            self.stdout.write(
                f"Granted document/image/media collection permissions and "
                f"{scope}-scoped {tier} page permissions to '{group_name}'"
            )
