"""
Data migration for issue #306: make the linked auth User the single source of
truth for member first_name / last_name / email.

For every Member WITH a linked User, the member's first_name, last_name and
email are copied onto the User. Copy precedence: a non-empty Member value wins
over the User value; an empty Member value never overwrites a non-empty User
value. When the email is copied, User.username is realigned to the new email
(the login identifier) unless another account already holds that username.

For every Member WITHOUT a linked User, a User is created so no name/email
data is lost when the columns are dropped in the following migration:
  - username: the member's email, or a name-derived slug when the member has
    no email; numeric suffixes resolve collisions (checked case-insensitively,
    which is safe on MySQL's case-insensitive unique index)
  - password: unusable (same as members.auth.create_member_user)
  - if a User already exists with username matching the member's email, that
    User is linked instead of creating a duplicate

Reverse is a no-op: the copied values are simply left on the User rows, and
the following schema migration restores the Member columns on rollback.
"""

from django.contrib.auth.hashers import make_password
from django.db import migrations
from django.utils.text import slugify


def _unique_username(User, email, first_name, last_name):
    base = (email or "").strip()
    if not base:
        base = slugify(f"{first_name} {last_name}".strip()) or "member"
    base = base[:140]
    username = base
    suffix = 2
    while User.objects.filter(username__iexact=username).exists():
        username = f"{base}-{suffix}"
        suffix += 1
    return username


def copy_member_fields_to_users(apps, schema_editor):
    Member = apps.get_model("blowcomotion", "Member")
    User = apps.get_model("auth", "User")

    for member in Member.objects.select_related("user").iterator():
        first_name = (member.first_name or "")[:150]
        last_name = (member.last_name or "")[:150]
        email = (member.email or "").strip()

        user = member.user
        if user is None:
            # Link an existing account with this email if there is one,
            # otherwise create an inactive-credential (unusable password) User.
            if email:
                user = User.objects.filter(username__iexact=email).first()
                if user is not None and Member.objects.filter(user=user).exists():
                    # Already claimed by another member (user is a OneToOne);
                    # give this member its own account instead.
                    user = None
            if user is None:
                user = User.objects.create(
                    username=_unique_username(User, email, first_name, last_name),
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    password=make_password(None),
                )
                member.user = user
                member.save(update_fields=["user"])
                continue
            member.user = user
            member.save(update_fields=["user"])

        update_fields = []
        # Prefer non-empty Member values; never clobber User values with blanks.
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            update_fields.append("first_name")
        if last_name and user.last_name != last_name:
            user.last_name = last_name
            update_fields.append("last_name")
        if email and user.email != email:
            user.email = email
            update_fields.append("email")
        # Staff/superuser accounts may deliberately log in with a non-email
        # username; only realign ordinary member accounts to the email.
        if email and not user.is_staff and not user.is_superuser:
            desired_username = email[:150]
            if user.username != desired_username:
                collision = (
                    User.objects.exclude(pk=user.pk)
                    .filter(username__iexact=desired_username)
                    .exists()
                )
                if not collision:
                    user.username = desired_username
                    update_fields.append("username")
        if update_fields:
            user.save(update_fields=update_fields)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("blowcomotion", "0127_backfill_conductor_charts"),
    ]

    operations = [
        migrations.RunPython(copy_member_fields_to_users, noop),
    ]
