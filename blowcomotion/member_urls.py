from django.contrib.auth import views as auth_views
from django.urls import path

from blowcomotion import member_views

urlpatterns = [
    path("login/", member_views.MemberLoginView.as_view(), name="member-login"),
    path("logout/", auth_views.LogoutView.as_view(), name="member-logout"),
    path("set-password/<uuid:token_uuid>/", member_views.set_password_view, name="member-set-password"),
    path("get-access/", member_views.get_access_view, name="member-get-access"),
    path("password-reset/", member_views.MemberPasswordResetView.as_view(), name="member-password-reset"),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="member/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "password-reset/confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="member/password_reset_confirm.html",
            success_url="/member/password-reset/complete/",
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(template_name="member/password_reset_complete.html"),
        name="password_reset_complete",
    ),
    # Portal views (added in Task 9)
    path("confirm-email/<uuid:token_uuid>/", member_views.confirm_email_view, name="member-confirm-email"),
    path("profile/", member_views.profile_view, name="member-profile"),
    path("attendance/", member_views.attendance_view, name="member-attendance"),
    path("requests/", member_views.requests_view, name="member-requests"),
    path("requests/<int:pk>/", member_views.rental_request_detail, name="member-rental-request-detail"),
    path("instrument-rental/", member_views.instrument_rental_request, name="member-instrument-rental"),
    path("", member_views.member_home, name="member-home"),
]
