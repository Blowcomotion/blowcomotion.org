from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from search import views as search_views
import blowcomotion.views as blowcomotion_views

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("admin/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("search/", search_views.search, name="search"),
    path("process-form/", blowcomotion_views.process_form, name="process-form"),
    
    # Attendance URLs
    path("attendance/", blowcomotion_views.attendance_capture, name="attendance-main"),
    path("attendance/reports/", blowcomotion_views.attendance_reports, name="attendance-reports"),
    path("attendance/reports/<str:section_slug>/", blowcomotion_views.attendance_section_report_new, name="attendance-section-report"),
    path("attendance/<str:section_slug>/", blowcomotion_views.attendance_capture, name="attendance-capture"),
    
    # Birthdays URL
    path("birthdays/", blowcomotion_views.birthdays, name="birthdays"),
]


if settings.DEBUG:
    from django.conf.urls.static import static
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    # Serve static and media files from development server
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns = urlpatterns + [
    # For anything not caught by a more specific rule above, hand over to
    # Wagtail's page serving mechanism. This should be the last pattern in
    # the list:
    path("", include(wagtail_urls)),
    # Alternatively, if you want Wagtail pages to be served from a subpath
    # of your site, rather than the site root:
    #    path("pages/", include(wagtail_urls)),
]
