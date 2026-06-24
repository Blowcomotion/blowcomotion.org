"""
One-off script: unlink User from members whose invite email failed so
invite_members can re-run for them.

Usage: python manage.py shell < unlink_failed_invites.py
"""
from django.contrib.auth import get_user_model

from blowcomotion.models import Member

FAILED_IDS = [316, 317, 318, 319, 320, 321, 323, 325, 326, 327]
User = get_user_model()

for member in Member.objects.filter(pk__in=FAILED_IDS).select_related("user"):
    user = member.user
    if user is None:
        print(f"SKIP (no user): {member} [{member.pk}]")
        continue
    member.user = None
    member.save(update_fields=["user"])
    user.delete()
    print(f"Unlinked + deleted user for: {member} [{member.pk}] <{member.email}>")

print("Done.")
