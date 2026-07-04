from django.urls import path

from attendance import views
from gigs import views as gigs_views

urlpatterns = [
    path("", views.attendance_capture, name="attendance-main"),
    path("reports/", views.attendance_reports, name="attendance-reports"),
    path("reports/<str:section_slug>/", views.attendance_section_report_new, name="attendance-section-report"),
    path("gigs-for-date/", gigs_views.gigs_for_date, name="gigs-for-date"),
    path("inactive-members/", views.inactive_members, name="inactive-members"),
    path("<str:section_slug>/", views.attendance_capture, name="attendance-capture"),
]
