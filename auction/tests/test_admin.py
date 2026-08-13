from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

User = get_user_model()


class AuctionAdminTests(TestCase):
    def test_auctioneer_can_load_auction_snippet_index(self):
        from django.contrib.auth.models import Group

        call_command("setup_roles", verbosity=0)
        user = User.objects.create_user(username="beej", password="Pass123!")
        user.groups.add(Group.objects.get(name="Auctioneer"))
        self.client.login(username="beej", password="Pass123!")
        response = self.client.get("/admin/snippets/auction/auction/")
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/admin/snippets/auction/auctionitem/")
        self.assertEqual(response.status_code, 200)
