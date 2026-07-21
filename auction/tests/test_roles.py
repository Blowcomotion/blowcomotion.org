from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase


class AuctioneerRoleTests(TestCase):
    def test_setup_roles_creates_auctioneer(self):
        call_command("setup_roles", verbosity=0)
        group = Group.objects.get(name="Auctioneer")
        codenames = set(group.permissions.values_list("codename", flat=True))
        self.assertIn("access_admin", codenames)
        for model in ("auction", "auctionitem", "auctionitemimage", "bidder", "bid"):
            self.assertIn(f"change_{model}", codenames)
        self.assertTrue(
            group.collection_permissions.filter(permission__codename="add_image").exists()
        )
