import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.template.loader import render_to_string

from blowcomotion.models import EmailChangeToken, Member, PasswordSetToken

logger = logging.getLogger(__name__)

User = get_user_model()


def create_member_user(member):
    """Create a Django User with unusable password linked to member. Returns existing if already linked."""
    if member.user_id:
        return member.user

    email = member.email or ""
    user = User.objects.create_user(username=email, email=email)
    user.set_unusable_password()
    user.save(update_fields=["password"])

    member.user = user
    member.save(update_fields=["user"], sync_go3=False)
    logger.info(f"Created user account for member {member.pk} ({email})")
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
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.FROM_EMAIL,
        recipient_list=[member.email],
        fail_silently=False,
    )
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
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.FROM_EMAIL,
        recipient_list=[new_email],
        fail_silently=False,
    )
    member.pending_email = new_email
    member.save(update_fields=["pending_email"], sync_go3=False)
    logger.info(f"Sent email-change confirmation to {new_email} for member {member.pk}")
