import email.policy
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from blowcomotion.models import EmailChangeToken, Member, PasswordSetToken

logger = logging.getLogger(__name__)

User = get_user_model()

# Django 6 uses email.policy.default (max_line_length=78) which triggers
# quoted-printable encoding for any line over 78 chars — breaking long URLs.
# RFC 5322 hard limit is 998; using that here so plain-text bodies are sent
# as 7bit without QP soft-wrapping.
_EMAIL_POLICY = email.policy.default.clone(max_line_length=998)


class _MemberEmail(EmailMessage):
    def message(self, *, policy=None):
        return super().message(policy=policy or _EMAIL_POLICY)


def _send_mail(subject, body, from_email, recipient):
    _MemberEmail(
        subject=subject,
        body=body,
        from_email=from_email,
        to=[recipient],
    ).send(fail_silently=False)


def needs_set_password(member):
    """True when the member must go through the set-password flow rather than password-reset."""
    return not member.user_id or not member.user.has_usable_password() or not member.is_active


def ensure_set_password_flow(member, request):
    """Create a User account if needed, then send the set-password email."""
    if not member.user_id:
        create_member_user(member)
    send_set_password_email(member, request)


def create_member_user(member):
    """Create a Django User with unusable password linked to member.

    Returns the existing linked User if already present. If a User with the
    member's email already exists in the auth system, links that User rather
    than raising IntegrityError. Raises ValueError if member has no email.
    """
    if member.user_id:
        return member.user

    email = (member.email or "").strip()
    if not email:
        raise ValueError(f"Cannot create user for member {member.pk}: no email address")

    user, created = User.objects.get_or_create(
        username=email,
        defaults={"email": email},
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    elif user.email != email:
        user.email = email
        user.save(update_fields=["email"])

    member.user = user
    member.save(update_fields=["user"], sync_go3=False)
    logger.info(f"{'Created' if created else 'Linked existing'} user account for member {member.pk} ({email})")
    return user


def _supersede_set_password_tokens(member):
    PasswordSetToken.objects.filter(
        member=member, used=False, superseded=False
    ).update(superseded=True)


def send_set_password_email(member, request):
    """Generate a PasswordSetToken and email member a direct set-password link."""
    _supersede_set_password_tokens(member)
    token = PasswordSetToken.objects.create(member=member)

    set_password_url = request.build_absolute_uri(
        f"/member/set-password/{token.uuid}/"
    )
    subject = "Set your Blowcomotion member password"
    message = render_to_string(
        "emails/set_password.txt",
        {"member": member, "set_password_url": set_password_url},
    )
    _send_mail(subject, message, settings.FROM_EMAIL, member.email)
    logger.info(f"Sent set-password email to member {member.pk} ({member.email})")


def send_email_change_confirmation(member, new_email, request):
    """Create an EmailChangeToken, set member.pending_email, and email new_email the confirm link."""
    EmailChangeToken.objects.filter(member=member, used=False).update(used=True)
    token = EmailChangeToken.objects.create(member=member, new_email=new_email)

    confirm_url = request.build_absolute_uri(f"/member/confirm-email/{token.uuid}/")
    subject = "Confirm your new Blowcomotion email address"
    message = render_to_string(
        "emails/email_change_confirm.txt",
        {"member": member, "new_email": new_email, "confirm_url": confirm_url},
    )
    _send_mail(subject, message, settings.FROM_EMAIL, new_email)
    member.pending_email = new_email
    member.save(update_fields=["pending_email"], sync_go3=False)
    logger.info(f"Sent email-change confirmation to {new_email} for member {member.pk}")


def send_signup_invite_email(email, request):
    """Send a signup link to an address not found in the member list.

    Suppressed for 24 hours after the first send to the same address to prevent
    the get-access endpoint from being used as an email spam relay.
    """
    cache_key = f"signup_invite:{email.lower()}"
    send_count = cache.get(cache_key, 0)
    if send_count >= 2:
        logger.debug(f"Signup invite suppressed for {email} (sent {send_count}x in past 24h)")
        return
    cache.set(cache_key, send_count + 1, timeout=86400)

    signup_url = request.build_absolute_uri("/member-signup/")
    subject = "Blowcomotion member portal access"
    message = render_to_string(
        "emails/member_signup_invite.txt",
        {"signup_url": signup_url},
    )
    _send_mail(subject, message, settings.FROM_EMAIL, email)
    logger.info(f"Sent signup invite to non-member address: {email}")
