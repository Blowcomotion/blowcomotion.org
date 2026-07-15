import email.policy
import logging
import threading

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.urls import reverse

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

    def send(self, fail_silently=False):
        result = super().send(fail_silently=fail_silently)
        extra = getattr(settings, "FORM_TEST_EMAIL", None)
        if extra and extra not in self.to:
            copy = _MemberEmail(subject=self.subject, body=self.body, from_email=self.from_email, to=[extra])
            EmailMessage.send(copy, fail_silently=True)
        return result


def _dispatch_email(email_message, fail_silently=False, background=False):
    """Send an EmailMessage, optionally off of the request/command thread.

    Runs synchronously whenever the locmem test backend is active, so tests
    can assert on mail.outbox immediately after the request/command returns.
    Otherwise, when background=True, sends from a daemon thread so a slow
    SMTP server can't stall the caller (e.g. a public form submission).

    background should only be True for request-serving code paths: a daemon
    thread is killed the instant its process exits, so one-shot management
    commands must keep sending synchronously to avoid dropping mail.
    """
    if not background or settings.EMAIL_BACKEND == "django.core.mail.backends.locmem.EmailBackend":
        email_message.send(fail_silently=fail_silently)
        return

    def _send():
        try:
            email_message.send(fail_silently=False)
        except Exception:
            logger.exception(
                "Background email send failed (subject=%r, to=%r)",
                email_message.subject, email_message.to,
            )

    threading.Thread(target=_send, daemon=True).start()


def _send_mail(subject, body, from_email, recipient, background=False):
    email_message = _MemberEmail(
        subject=subject,
        body=body,
        from_email=from_email,
        to=[recipient],
    )
    _dispatch_email(email_message, fail_silently=False, background=background)


def needs_set_password(member):
    """True when the member must go through the set-password flow rather than password-reset."""
    return not member.user_id or not member.user.has_usable_password() or not member.is_active


def ensure_set_password_flow(member, base_url):
    """Create a User account if needed, then send the set-password email."""
    if not member.user_id:
        create_member_user(member)
    send_set_password_email(member, base_url)


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


def send_set_password_email(member, base_url):
    """Generate a PasswordSetToken and email member a direct set-password link."""
    _supersede_set_password_tokens(member)
    token = PasswordSetToken.objects.create(member=member)

    set_password_url = f"{base_url}/member/set-password/{token.uuid}/"
    subject = "Set your Blowcomotion member password"
    message = render_to_string(
        "emails/set_password.txt",
        {"member": member, "set_password_url": set_password_url},
    )
    _send_mail(subject, message, settings.FROM_EMAIL, member.email)
    logger.info(f"Sent set-password email to member {member.pk} ({member.email})")


def send_email_change_confirmation(member, new_email, base_url):
    """Create an EmailChangeToken, set member.pending_email, and email new_email the confirm link."""
    EmailChangeToken.objects.filter(member=member, used=False).update(used=True)
    token = EmailChangeToken.objects.create(member=member, new_email=new_email)

    confirm_url = f"{base_url}/member/confirm-email/{token.uuid}/"
    subject = "Confirm your new Blowcomotion email address"
    message = render_to_string(
        "emails/email_change_confirm.txt",
        {"member": member, "new_email": new_email, "confirm_url": confirm_url},
    )
    _send_mail(subject, message, settings.FROM_EMAIL, new_email)
    member.pending_email = new_email
    member.save(update_fields=["pending_email"], sync_go3=False)
    logger.info(f"Sent email-change confirmation to {new_email} for member {member.pk}")


def send_member_signup_welcome_email(member, base_url, background=False):
    """Create a PasswordSetToken and email the new member a welcome with both next steps.

    background=True sends the email from a daemon thread so a slow SMTP
    server doesn't stall the signup request; pass it only from request-serving
    call sites (see _dispatch_email).
    """
    _supersede_set_password_tokens(member)
    token = PasswordSetToken.objects.create(member=member)
    set_password_url = f"{base_url}/member/set-password/{token.uuid}/"
    subject = "Welcome to Blowcomotion - Next Steps"
    message = render_to_string(
        "emails/member_signup_welcome.txt",
        {
            "member": member,
            "set_password_url": set_password_url,
            "get_access_url": f"{base_url}{reverse('member-get-access')}",
        },
    )
    _send_mail(subject, message, settings.FROM_EMAIL, member.email, background=background)
    logger.info(f"Sent signup welcome email to member {member.pk} ({member.email})")


def send_signup_invite_email(email, base_url):
    """Send a signup link to an address not found in the member list.

    Suppressed for 24 hours after the first send to the same address to prevent
    the get-access endpoint from being used as an email spam relay.
    """
    cache_key = f"signup_invite:{email.lower()}"
    send_count = cache.get(cache_key, 0)
    if send_count >= 2:
        logger.info(f"Signup invite suppressed for {email} (sent {send_count}x in past 24h)")
        return
    cache.set(cache_key, send_count + 1, timeout=86400)

    signup_url = f"{base_url}/member-signup/"
    subject = "Blowcomotion member portal access"
    message = render_to_string(
        "emails/member_signup_invite.txt",
        {"signup_url": signup_url},
    )
    _send_mail(subject, message, settings.FROM_EMAIL, email)
    logger.info(f"Sent signup invite to non-member address: {email}")
