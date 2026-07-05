# Silent Auction App Implementation Plan (issue #116)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A silent-auction system: Auctioneer-managed items with image carousels, public bidding via web and SMS (Twilio), outbid/winner notifications, automatic winner + silent backup selection at deadline, per-event reset, historical results.

**Architecture:** New `auction` Django app with its own `models.py`/migrations (allowed for new domains per CLAUDE.md). Wagtail snippets for admin (gated by a new Auctioneer group), a StreamField `AuctionBlock` renders the item grid on CMS pages, Django views handle item detail/bids/Twilio webhook, a management command + lazy per-request closing picks winners. Spec: `docs/superpowers/specs/2026-07-05-auction-app-design.md`.

**Tech Stack:** Django 6 / Wagtail 7.4, Bootstrap 5 (dark theme), htmx (grid polling only), Twilio REST API + inbound webhook, existing `_MemberEmail` for email.

## Global Constraints

- Work on branch `feature/issue-116-auction-app` (create from `development`; no `claude/` prefix).
- GPG-sign every commit: `git commit -S`. No emojis. Conventional prefixes (`feat:`, `fix:`, `chore:`, `docs:`). No `Co-Authored-By`.
- isort runs via pre-commit hook; if it rejects, run `isort blowcomotion/ auction/` and re-stage.
- Every public POST view calls `_validate_recaptcha(request)` (from `blowcomotion.views`) before processing; public forms carry `data-recaptcha` and pages pass `include_form_js=True`.
- All email goes through `_MemberEmail` (`members.auth`) — it centrally copies `FORM_TEST_EMAIL`. Never use raw `send_mail`.
- Static sources live under `blowcomotion/static/`, never `static/`. Do NOT run collectstatic locally.
- Twilio settings are optional: `getattr(settings, "TWILIO_ACCOUNT_SID", None)` etc.; absent → SMS skipped silently, email still sent.
- Run tests with output piped to a scratch file, then read the tail — never re-run just because output scrolled:
  `python manage.py test auction -v 2 > "$SCRATCH/testout.txt" 2>&1; tail -30 "$SCRATCH/testout.txt"`

## Subagent Orchestration

Dispatch one fresh subagent per task via superpowers:subagent-driven-development, with per-task `model`:

| Task | Model | Why |
|------|-------|-----|
| 1 models, 4 notifications, 7 block/templates, 9 manage+promote, 10 snippets | sonnet | standard Django/Wagtail with exact code provided |
| 2 role, 11 seed command | haiku | mechanical, pattern fully specified |
| 3 bid service, 5 closing, 6 identity+bid views, 8 SMS webhook | opus | money, concurrency, and trust-boundary logic |
| 12 integration + PR | main session | judgment + user-facing |

Each subagent must pipe long command output to `$SCRATCH` files (scratchpad path from its environment) and read the tail, not re-run commands.

---

### Task 1: App scaffold, models, migration (sonnet)

**Files:**
- Create: `auction/__init__.py` (empty), `auction/apps.py`, `auction/models.py`, `auction/migrations/` (via makemigrations), `auction/tests/__init__.py` (empty), `auction/tests/test_models.py`
- Modify: `blowcomotion/settings/base.py` (INSTALLED_APPS — add `"auction",` after `"members",` at line 37)

**Interfaces:**
- Produces: `Auction`, `AuctionItem` (`.effective_close_time`, `.is_open`, `.top_bid`, `.minimum_bid`, auto-assigned `.number`), `AuctionItemImage`, `Bidder` (`.display_name`, phone normalized on save), `Bid`, `normalize_phone(raw) -> "+1XXXXXXXXXX"` raising `ValidationError`.

- [ ] **Step 1: Write the failing tests**

`auction/tests/test_models.py`:

```python
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from auction.models import (
    Auction,
    AuctionItem,
    Bid,
    Bidder,
    normalize_phone,
)


def make_auction(**kwargs):
    defaults = dict(name="Fall Fundraiser", close_time=timezone.now() + timedelta(days=7))
    defaults.update(kwargs)
    return Auction.objects.create(**defaults)


def make_item(auction, **kwargs):
    defaults = dict(title="Yeti Cooler", starting_bid=Decimal("25"), bid_increment=Decimal("5"))
    defaults.update(kwargs)
    return AuctionItem.objects.create(auction=auction, **defaults)


def make_bidder(auction, **kwargs):
    defaults = dict(name="Robin Player", email="robin@example.com", phone="512-555-1234")
    defaults.update(kwargs)
    return Bidder.objects.create(auction=auction, **defaults)


class PhoneNormalizationTests(TestCase):
    def test_ten_digit_us(self):
        self.assertEqual(normalize_phone("512-555-1234"), "+15125551234")

    def test_eleven_digit_with_country_code(self):
        self.assertEqual(normalize_phone("1 (512) 555-1234"), "+15125551234")

    def test_international_plus_kept(self):
        self.assertEqual(normalize_phone("+44 20 7946 0958"), "+442079460958")

    def test_garbage_raises(self):
        with self.assertRaises(ValidationError):
            normalize_phone("123")


class AuctionItemTests(TestCase):
    def setUp(self):
        self.auction = make_auction()

    def test_number_auto_assigned_sequentially(self):
        a = make_item(self.auction)
        b = make_item(self.auction, title="Gift Card")
        self.assertEqual((a.number, b.number), (1, 2))

    def test_effective_close_time_falls_back_to_auction(self):
        item = make_item(self.auction)
        self.assertEqual(item.effective_close_time, self.auction.close_time)
        override = timezone.now() + timedelta(days=9)
        item.close_time = override
        self.assertEqual(item.effective_close_time, override)

    def test_minimum_bid_starting_then_increment(self):
        item = make_item(self.auction)
        self.assertEqual(item.minimum_bid, Decimal("25"))
        bidder = make_bidder(self.auction)
        Bid.objects.create(item=item, bidder=bidder, amount=Decimal("30"))
        self.assertEqual(item.top_bid.amount, Decimal("30"))
        self.assertEqual(item.minimum_bid, Decimal("35"))


class BidderTests(TestCase):
    def setUp(self):
        self.auction = make_auction()

    def test_phone_normalized_on_save(self):
        bidder = make_bidder(self.auction)
        self.assertEqual(bidder.phone, "+15125551234")

    def test_display_name(self):
        self.assertEqual(make_bidder(self.auction).display_name, "Robin P.")

    def test_phone_unique_per_auction(self):
        make_bidder(self.auction)
        with self.assertRaises(Exception):
            make_bidder(self.auction, email="other@example.com")

    def test_same_phone_ok_in_other_auction(self):
        make_bidder(self.auction)
        other = make_auction(name="Spring Fundraiser")
        self.assertIsNotNone(make_bidder(other))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test auction -v 2 > "$SCRATCH/t1-fail.txt" 2>&1; tail -15 "$SCRATCH/t1-fail.txt"
```
Expected: import error (`No module named 'auction'` / models missing).

- [ ] **Step 3: Implement**

`auction/apps.py`:

```python
from django.apps import AppConfig


class AuctionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "auction"
```

`auction/models.py`:

```python
import re

from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.images import get_image_model_string
from wagtail.models import Orderable

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Max
from django.utils import timezone


def normalize_phone(raw):
    """Normalize to E.164 so Twilio 'From' matching works. US default."""
    digits = re.sub(r"\D", "", raw or "")
    if (raw or "").strip().startswith("+") and len(digits) >= 8:
        return "+" + digits
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    raise ValidationError("Enter a valid phone number (10 digits for US).")


class Auction(ClusterableModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    close_time = models.DateTimeField(
        help_text="When bidding closes. Individual items may run longer if soft close extends them."
    )
    soft_close_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Anti-sniping: a bid placed in the final minutes pushes that item's "
            "deadline out by the same window, so auctions end when bidding truly stops."
        ),
    )
    soft_close_minutes = models.PositiveIntegerField(default=5)
    payment_instructions = models.TextField(
        blank=True, help_text="Included in winner notifications (where/how to pay and pick up)."
    )
    summary_sent_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class AuctionItem(ClusterableModel):
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name="items")
    number = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Item number used on printed cards and in SMS bids (auto-assigned if blank).",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    starting_bid = models.DecimalField(max_digits=8, decimal_places=2)
    bid_increment = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    close_time = models.DateTimeField(
        null=True, blank=True, help_text="Leave blank to use the auction's close time."
    )
    winning_bid = models.ForeignKey(
        "auction.Bid", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    backup_bid = models.ForeignKey(
        "auction.Bid", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    winner_notified_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(fields=["auction", "number"], name="unique_item_number_per_auction"),
        ]

    def __str__(self):
        return f"#{self.number} {self.title}"

    def save(self, *args, **kwargs):
        if self.number is None:
            current = AuctionItem.objects.filter(auction=self.auction).aggregate(m=Max("number"))["m"] or 0
            self.number = current + 1
        super().save(*args, **kwargs)

    @property
    def effective_close_time(self):
        return self.close_time or self.auction.close_time

    @property
    def is_open(self):
        return self.winner_notified_at is None and self.effective_close_time > timezone.now()

    @property
    def top_bid(self):
        return self.bids.order_by("-amount", "created_at").first()

    @property
    def minimum_bid(self):
        top = self.top_bid
        return top.amount + self.bid_increment if top else self.starting_bid


class AuctionItemImage(Orderable):
    item = ParentalKey(AuctionItem, on_delete=models.CASCADE, related_name="images")
    image = models.ForeignKey(get_image_model_string(), on_delete=models.CASCADE, related_name="+")

    panels = ["image"]


class Bidder(models.Model):
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name="bidders")
    member = models.ForeignKey(
        "blowcomotion.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="auction_bidders"
    )
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    sms_opt_in = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["auction", "phone"], name="unique_bidder_phone_per_auction"),
            models.UniqueConstraint(fields=["auction", "email"], name="unique_bidder_email_per_auction"),
            models.UniqueConstraint(
                fields=["auction", "member"],
                condition=models.Q(member__isnull=False),
                name="unique_bidder_member_per_auction",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.auction})"

    def save(self, *args, **kwargs):
        self.phone = normalize_phone(self.phone)
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        parts = self.name.split()
        if len(parts) > 1:
            return f"{parts[0]} {parts[-1][0]}."
        return self.name


class Bid(models.Model):
    SOURCE_WEB = "web"
    SOURCE_SMS = "sms"
    item = models.ForeignKey(AuctionItem, on_delete=models.CASCADE, related_name="bids")
    bidder = models.ForeignKey(Bidder, on_delete=models.CASCADE, related_name="bids")
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    source = models.CharField(
        max_length=3, choices=[(SOURCE_WEB, "Web"), (SOURCE_SMS, "SMS")], default=SOURCE_WEB
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"${self.amount} on {self.item} by {self.bidder.display_name}"
```

Add `"auction",` to `INSTALLED_APPS` in `blowcomotion/settings/base.py` directly after `"members",`.

- [ ] **Step 4: Make migration, run tests**

```bash
python manage.py makemigrations auction > "$SCRATCH/t1-mig.txt" 2>&1; tail -10 "$SCRATCH/t1-mig.txt"
python manage.py test auction -v 2 > "$SCRATCH/t1-pass.txt" 2>&1; tail -15 "$SCRATCH/t1-pass.txt"
```
Expected: one migration `auction/migrations/0001_initial.py`; all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add auction/ blowcomotion/settings/base.py
git commit -S -m "feat: add auction app with core models (issue #116)"
```

---

### Task 2: Auctioneer role (haiku)

**Files:**
- Modify: `blowcomotion/management/commands/setup_roles.py`
- Test: `auction/tests/test_roles.py`

**Interfaces:**
- Produces: "Auctioneer" Group with CRUD perms on all five auction models, Wagtail admin access, and image collection perms (add/change/view/choose) at the root collection.

- [ ] **Step 1: Write the failing test**

`auction/tests/test_roles.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python manage.py test auction.tests.test_roles -v 2 > "$SCRATCH/t2.txt" 2>&1; tail -10 "$SCRATCH/t2.txt"
```
Expected: FAIL — `Group matching query does not exist`.

- [ ] **Step 3: Implement**

In `setup_roles.py`, add below the existing `from blowcomotion.models import (...)` import:

```python
from auction.models import Auction, AuctionItem, AuctionItemImage, Bid, Bidder
```

(isort will place it — `auction` sorts before `blowcomotion`.)

Add to `ROLE_PERMISSIONS` after the `"Attendance Taker"` entry:

```python
    # Grants admin access to the auction snippets and gates the auction
    # manage/promote views, which check change_auctionitem.
    "Auctioneer": lambda: (
        _model_perms(Auction)
        + _model_perms(AuctionItem)
        + _model_perms(AuctionItemImage)
        + _model_perms(Bidder)
        + _model_perms(Bid)
        + ACCESS_ADMIN()
    ),
```

In `Command.handle`, after the `for name, get_perms in ROLE_PERMISSIONS.items():` loop and before `self._patch_editor_groups()`, add:

```python
        # Auctioneers upload item photos, so they need image permissions on
        # the root collection (flat model perms are not enough for choosers).
        auctioneer = Group.objects.get(name="Auctioneer")
        _grant_collection_perms(
            auctioneer,
            Collection.get_first_root_node(),
            {WagtailImage: ("add", "change", "view", "choose")},
        )
        self.stdout.write("Granted image collection permissions to 'Auctioneer'")
```

- [ ] **Step 4: Run tests**

```bash
python manage.py test auction.tests.test_roles -v 2 > "$SCRATCH/t2.txt" 2>&1; tail -10 "$SCRATCH/t2.txt"
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add blowcomotion/management/commands/setup_roles.py auction/tests/test_roles.py
git commit -S -m "feat: add Auctioneer role gating auction admin"
```

---

### Task 3: Bid placement service (opus)

**Files:**
- Create: `auction/services.py`, `auction/tests/test_services.py`

**Interfaces:**
- Consumes: Task 1 models.
- Produces: `BidError(Exception)` with user-facing `str()`; `place_bid(item_id, bidder, amount, source="web") -> Bid` (row-locks the item, validates open + minimum, applies soft close, queues outbid notification via `transaction.on_commit`). Notification call target is `auction.notifications.notify_outbid(previous_top_bid, new_bid)` (Task 4) — import it lazily inside the function so Tasks 3/4 can land in either order with tests mocking `auction.services._get_notify_outbid()`; simplest: `from auction import notifications` inside `place_bid` and call `notifications.notify_outbid(...)`; tests `@patch("auction.notifications.notify_outbid")`. If Task 4 hasn't landed, create a stub `auction/notifications.py` containing `def notify_outbid(previous_top_bid, new_bid): pass` so imports resolve.

- [ ] **Step 1: Write the failing tests**

`auction/tests/test_services.py`:

```python
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from auction.models import Bid
from auction.services import BidError, place_bid
from auction.tests.test_models import make_auction, make_bidder, make_item


@patch("auction.notifications.notify_outbid")
class PlaceBidTests(TestCase):
    def setUp(self):
        self.auction = make_auction()
        self.item = make_item(self.auction)  # starting 25, increment 5
        self.alice = make_bidder(self.auction)
        self.bob = make_bidder(self.auction, name="Bob Jones", email="bob@example.com", phone="512-555-9999")

    def test_first_bid_must_meet_starting_bid(self, mock_notify):
        with self.assertRaises(BidError):
            place_bid(self.item.pk, self.alice, Decimal("20"))
        bid = place_bid(self.item.pk, self.alice, Decimal("25"))
        self.assertEqual(bid.amount, Decimal("25"))
        mock_notify.assert_not_called()

    def test_subsequent_bid_needs_increment_and_notifies_previous_leader(self, mock_notify):
        first = place_bid(self.item.pk, self.alice, Decimal("25"))
        with self.assertRaises(BidError):
            place_bid(self.item.pk, self.bob, Decimal("29"))
        with self.captureOnCommitCallbacks(execute=True):
            place_bid(self.item.pk, self.bob, Decimal("30"))
        mock_notify.assert_called_once()
        self.assertEqual(mock_notify.call_args.args[0], first)

    def test_self_outbid_sends_no_notification(self, mock_notify):
        place_bid(self.item.pk, self.alice, Decimal("25"))
        with self.captureOnCommitCallbacks(execute=True):
            place_bid(self.item.pk, self.alice, Decimal("30"))
        mock_notify.assert_not_called()

    def test_closed_item_rejects_bids(self, mock_notify):
        self.item.close_time = timezone.now() - timedelta(minutes=1)
        self.item.save()
        with self.assertRaises(BidError):
            place_bid(self.item.pk, self.alice, Decimal("25"))

    def test_soft_close_extends_deadline(self, mock_notify):
        self.auction.soft_close_enabled = True
        self.auction.soft_close_minutes = 5
        self.auction.save()
        self.item.close_time = timezone.now() + timedelta(minutes=2)
        self.item.save()
        place_bid(self.item.pk, self.alice, Decimal("25"))
        self.item.refresh_from_db()
        remaining = self.item.close_time - timezone.now()
        self.assertGreater(remaining, timedelta(minutes=4))

    def test_no_soft_close_when_disabled(self, mock_notify):
        original = self.item.effective_close_time
        place_bid(self.item.pk, self.alice, Decimal("25"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.effective_close_time, original)

    def test_sms_source_recorded(self, mock_notify):
        bid = place_bid(self.item.pk, self.alice, Decimal("25"), source=Bid.SOURCE_SMS)
        self.assertEqual(bid.source, "sms")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test auction.tests.test_services -v 2 > "$SCRATCH/t3.txt" 2>&1; tail -10 "$SCRATCH/t3.txt"
```
Expected: FAIL — no module `auction.services`.

- [ ] **Step 3: Implement**

`auction/services.py`:

```python
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from auction.models import AuctionItem, Bid


class BidError(Exception):
    """User-facing bid rejection; str(exc) is safe to show/text back."""


def place_bid(item_id, bidder, amount, source=Bid.SOURCE_WEB):
    with transaction.atomic():
        item = (
            AuctionItem.objects.select_for_update()
            .select_related("auction")
            .get(pk=item_id)
        )
        now = timezone.now()
        if item.winner_notified_at or item.effective_close_time <= now:
            raise BidError(f"Bidding on #{item.number} {item.title} has closed.")
        previous_top = item.top_bid
        minimum = item.minimum_bid
        if amount < minimum:
            raise BidError(f"Your bid on #{item.number} must be at least ${minimum}.")
        bid = Bid.objects.create(item=item, bidder=bidder, amount=amount, source=source)

        auction = item.auction
        if auction.soft_close_enabled:
            window = timedelta(minutes=auction.soft_close_minutes)
            if item.effective_close_time - now < window:
                item.close_time = now + window
                item.save(update_fields=["close_time"])

        if previous_top and previous_top.bidder_id != bidder.pk:
            from auction import notifications

            transaction.on_commit(lambda: notifications.notify_outbid(previous_top, bid))
        return bid
```

If `auction/notifications.py` does not exist yet, create the one-line stub described in Interfaces.

- [ ] **Step 4: Run tests**

```bash
python manage.py test auction.tests.test_services -v 2 > "$SCRATCH/t3.txt" 2>&1; tail -10 "$SCRATCH/t3.txt"
```
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add auction/services.py auction/tests/test_services.py auction/notifications.py
git commit -S -m "feat: add row-locked bid placement with soft close"
```

---

### Task 4: Notifications module + Twilio dependency (sonnet)

**Files:**
- Create/replace: `auction/notifications.py`, `auction/tests/test_notifications.py`
- Modify: `requirements.txt` (append `twilio`)

**Interfaces:**
- Consumes: models; `_MemberEmail` from `members.auth`; Wagtail `Site` for absolute URLs.
- Produces:
  - `item_url(item) -> str` absolute URL `<root>/auction/<auction_id>/item/<number>/`
  - `send_sms(to_phone, body)` — no-op unless `TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`/`TWILIO_FROM_NUMBER` all set; never raises (logs failures)
  - `notify_outbid(previous_top_bid, new_bid)` — email always, SMS if `sms_opt_in`
  - `notify_winner(item)` — email + SMS to `item.winning_bid.bidder` with `payment_instructions`
  - `send_auction_summary(auction)` — emails users in the Auctioneer group (items, winners, amounts, total)

- [ ] **Step 1: Write the failing tests**

`auction/tests/test_notifications.py`:

```python
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings

from auction import notifications
from auction.models import Bid
from auction.tests.test_models import make_auction, make_bidder, make_item


class NotificationTests(TestCase):
    def setUp(self):
        self.auction = make_auction(payment_instructions="Pay at the merch table.")
        self.item = make_item(self.auction)
        self.alice = make_bidder(self.auction, sms_opt_in=True)
        self.bob = make_bidder(self.auction, name="Bob Jones", email="bob@example.com", phone="512-555-9999")
        self.first = Bid.objects.create(item=self.item, bidder=self.alice, amount=Decimal("25"))
        self.second = Bid.objects.create(item=self.item, bidder=self.bob, amount=Decimal("30"))

    @patch("auction.notifications.send_sms")
    def test_outbid_sends_email_and_sms_when_opted_in(self, mock_sms):
        notifications.notify_outbid(self.first, self.second)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("robin@example.com", mail.outbox[0].to)
        self.assertIn("outbid", mail.outbox[0].subject.lower())
        mock_sms.assert_called_once()
        body = mock_sms.call_args.args[1]
        self.assertIn("BID 1 35", body)          # next minimum: 30 + 5
        self.assertIn("/auction/", body)          # item link included

    @patch("auction.notifications.send_sms")
    def test_outbid_no_sms_without_opt_in(self, mock_sms):
        notifications.notify_outbid(self.second, self.first)  # bob has sms_opt_in=False
        mock_sms.assert_not_called()

    @patch("auction.notifications.send_sms")
    def test_winner_notice_includes_payment_instructions(self, mock_sms):
        self.item.winning_bid = self.second
        self.item.save()
        notifications.notify_winner(self.item)
        self.assertIn("merch table", mail.outbox[0].body)

    def test_send_sms_noop_without_settings(self):
        notifications.send_sms("+15125551234", "hello")  # must not raise

    @override_settings(
        TWILIO_ACCOUNT_SID="sid", TWILIO_AUTH_TOKEN="tok", TWILIO_FROM_NUMBER="+15550000000"
    )
    @patch("auction.notifications.Client")
    def test_send_sms_calls_twilio(self, mock_client):
        notifications.send_sms("+15125551234", "hello")
        mock_client.assert_called_once_with("sid", "tok")
        mock_client.return_value.messages.create.assert_called_once_with(
            to="+15125551234", from_="+15550000000", body="hello"
        )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pip install twilio > "$SCRATCH/t4-pip.txt" 2>&1; tail -3 "$SCRATCH/t4-pip.txt"
python manage.py test auction.tests.test_notifications -v 2 > "$SCRATCH/t4.txt" 2>&1; tail -10 "$SCRATCH/t4.txt"
```
Expected: FAIL — functions missing from the stub module.

- [ ] **Step 3: Implement**

Append `twilio` on its own line to `requirements.txt`. Replace `auction/notifications.py`:

```python
import logging

from twilio.rest import Client
from wagtail.models import Site

from django.conf import settings
from django.contrib.auth.models import Group

from members.auth import _MemberEmail

logger = logging.getLogger(__name__)


def _root_url():
    site = Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    return site.root_url if site else ""


def item_url(item):
    return f"{_root_url()}/auction/{item.auction_id}/item/{item.number}/"


def send_sms(to_phone, body):
    sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
    token = getattr(settings, "TWILIO_AUTH_TOKEN", None)
    from_number = getattr(settings, "TWILIO_FROM_NUMBER", None)
    if not (sid and token and from_number):
        logger.debug("Twilio not configured; SMS to %s skipped", to_phone)
        return
    try:
        Client(sid, token).messages.create(to=to_phone, from_=from_number, body=body)
    except Exception:
        logger.exception("Failed to send SMS to %s", to_phone)


def _send_email(subject, body, to):
    _MemberEmail(
        subject=subject, body=body, from_email=settings.FROM_EMAIL, to=to
    ).send(fail_silently=True)


def notify_outbid(previous_top_bid, new_bid):
    item = new_bid.item
    bidder = previous_top_bid.bidder
    url = item_url(item)
    next_min = item.minimum_bid
    _send_email(
        subject=f"You've been outbid on #{item.number} {item.title}",
        body=(
            f"Hi {bidder.name},\n\n"
            f"Someone bid ${new_bid.amount} on #{item.number} {item.title} — "
            f"you're no longer in the lead.\n\n"
            f"Bid again (at least ${next_min}): {url}\n"
        ),
        to=[bidder.email],
    )
    if bidder.sms_opt_in:
        send_sms(
            bidder.phone,
            f"You've been outbid on #{item.number} {item.title} — now ${new_bid.amount}. "
            f"Reply BID {item.number} {next_min} to retake the lead, or see it here: {url}",
        )


def notify_winner(item):
    bid = item.winning_bid
    if not bid:
        return
    bidder = bid.bidder
    instructions = item.auction.payment_instructions or ""
    _send_email(
        subject=f"You won #{item.number} {item.title}!",
        body=(
            f"Congratulations {bidder.name}!\n\n"
            f"You won #{item.number} {item.title} with a bid of ${bid.amount}.\n\n"
            f"{instructions}\n\n{item_url(item)}\n"
        ),
        to=[bidder.email],
    )
    if bidder.sms_opt_in:
        send_sms(
            bidder.phone,
            f"You won #{item.number} {item.title} for ${bid.amount}! {instructions}".strip(),
        )


def send_auction_summary(auction):
    try:
        group = Group.objects.get(name="Auctioneer")
    except Group.DoesNotExist:
        return
    recipients = [e for e in group.user_set.values_list("email", flat=True) if e]
    if not recipients:
        return
    lines, total = [], 0
    for item in auction.items.order_by("number"):
        if item.winning_bid:
            total += item.winning_bid.amount
            backup = item.backup_bid
            lines.append(
                f"#{item.number} {item.title}: ${item.winning_bid.amount} — "
                f"{item.winning_bid.bidder.name} ({item.winning_bid.bidder.email}, {item.winning_bid.bidder.phone})"
                + (f" [backup: {backup.bidder.name} ${backup.amount}]" if backup else "")
            )
        else:
            lines.append(f"#{item.number} {item.title}: no bids")
    body = f"{auction.name} — final results\n\n" + "\n".join(lines) + f"\n\nTotal raised: ${total}\n"
    _send_email(subject=f"Auction results: {auction.name}", body=body, to=recipients)
```

- [ ] **Step 4: Run tests (services suite too — the stub was replaced)**

```bash
python manage.py test auction -v 2 > "$SCRATCH/t4.txt" 2>&1; tail -15 "$SCRATCH/t4.txt"
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add auction/notifications.py auction/tests/test_notifications.py requirements.txt
git commit -S -m "feat: add auction email/SMS notifications via Twilio"
```

---

### Task 5: Winner selection — closing service + management command (opus)

**Files:**
- Modify: `auction/services.py`
- Create: `auction/management/__init__.py`, `auction/management/commands/__init__.py` (both empty), `auction/management/commands/close_auction_items.py`, `auction/tests/test_closing.py`

**Interfaces:**
- Consumes: Task 3 services, Task 4 `notify_winner`/`send_auction_summary`.
- Produces: `close_expired_items(auction=None) -> int` (count closed) in `auction/services.py`. Idempotent: only touches rows with `winner_notified_at` null whose effective close time passed; row-locked; sets `winning_bid`, `backup_bid` (highest bid by a different bidder), stamps `winner_notified_at`, queues `notify_winner` on commit; when an auction has no unprocessed items left and `summary_sent_at` is null, sends summary and stamps it. Command `python manage.py close_auction_items` wraps it.

- [ ] **Step 1: Write the failing tests**

`auction/tests/test_closing.py`:

```python
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from auction.models import Bid
from auction.services import close_expired_items
from auction.tests.test_models import make_auction, make_bidder, make_item


@patch("auction.notifications.send_auction_summary")
@patch("auction.notifications.notify_winner")
class CloseExpiredItemsTests(TestCase):
    def setUp(self):
        self.auction = make_auction(close_time=timezone.now() - timedelta(minutes=1))
        self.item = make_item(self.auction)
        self.alice = make_bidder(self.auction)
        self.bob = make_bidder(self.auction, name="Bob Jones", email="bob@example.com", phone="512-555-9999")

    def _close(self):
        with self.captureOnCommitCallbacks(execute=True):
            return close_expired_items()

    def test_picks_winner_and_backup(self, mock_winner, mock_summary):
        Bid.objects.create(item=self.item, bidder=self.alice, amount=Decimal("25"))
        Bid.objects.create(item=self.item, bidder=self.bob, amount=Decimal("30"))
        Bid.objects.create(item=self.item, bidder=self.alice, amount=Decimal("35"))
        closed = self._close()
        self.item.refresh_from_db()
        self.assertEqual(closed, 1)
        self.assertEqual(self.item.winning_bid.bidder, self.alice)
        self.assertEqual(self.item.winning_bid.amount, Decimal("35"))
        self.assertEqual(self.item.backup_bid.bidder, self.bob)  # highest by a DIFFERENT bidder
        mock_winner.assert_called_once_with(self.item)

    def test_no_bids_closes_silently(self, mock_winner, mock_summary):
        self._close()
        self.item.refresh_from_db()
        self.assertIsNotNone(self.item.winner_notified_at)
        self.assertIsNone(self.item.winning_bid)
        mock_winner.assert_not_called()

    def test_idempotent(self, mock_winner, mock_summary):
        Bid.objects.create(item=self.item, bidder=self.alice, amount=Decimal("25"))
        self._close()
        self.assertEqual(self._close(), 0)
        mock_winner.assert_called_once()

    def test_open_items_untouched(self, mock_winner, mock_summary):
        self.item.close_time = timezone.now() + timedelta(days=1)
        self.item.save()
        self.assertEqual(self._close(), 0)

    def test_summary_sent_once_when_auction_fully_closed(self, mock_winner, mock_summary):
        self._close()
        mock_summary.assert_called_once_with(self.auction)
        self._close()
        mock_summary.assert_called_once()

    def test_management_command_runs(self, mock_winner, mock_summary):
        call_command("close_auction_items")
        self.item.refresh_from_db()
        self.assertIsNotNone(self.item.winner_notified_at)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test auction.tests.test_closing -v 2 > "$SCRATCH/t5.txt" 2>&1; tail -10 "$SCRATCH/t5.txt"
```
Expected: FAIL — `close_expired_items` not defined.

- [ ] **Step 3: Implement**

Append to `auction/services.py`:

```python
def close_expired_items(auction=None):
    """Pick winner + backup for every expired, unprocessed item. Idempotent."""
    from django.db.models import Q

    from auction import notifications
    from auction.models import Auction

    now = timezone.now()
    closed = 0
    qs = AuctionItem.objects.filter(winner_notified_at__isnull=True).filter(
        Q(close_time__lte=now) | Q(close_time__isnull=True, auction__close_time__lte=now)
    )
    if auction is not None:
        qs = qs.filter(auction=auction)
    touched_auction_ids = set()
    with transaction.atomic():
        for item in qs.select_for_update().select_related("auction"):
            top = item.top_bid
            if top:
                item.winning_bid = top
                item.backup_bid = (
                    item.bids.exclude(bidder=top.bidder).order_by("-amount", "created_at").first()
                )
            item.winner_notified_at = now
            item.save(update_fields=["winning_bid", "backup_bid", "winner_notified_at"])
            touched_auction_ids.add(item.auction_id)
            closed += 1
            if top:
                transaction.on_commit(lambda i=item: notifications.notify_winner(i))
        for a in Auction.objects.select_for_update().filter(
            pk__in=touched_auction_ids, summary_sent_at__isnull=True
        ):
            if not a.items.filter(winner_notified_at__isnull=True).exists():
                a.summary_sent_at = now
                a.save(update_fields=["summary_sent_at"])
                transaction.on_commit(lambda a=a: notifications.send_auction_summary(a))
    return closed
```

`auction/management/commands/close_auction_items.py`:

```python
"""
Close expired auction items: pick winners/backups and send notifications.

Cron (hourly backstop; page views also close lazily):
0 * * * * cd /path/to/project && /path/to/venv/bin/python manage.py close_auction_items
"""
from django.core.management.base import BaseCommand

from auction.services import close_expired_items


class Command(BaseCommand):
    help = "Pick winners for expired auction items and send notifications"

    def handle(self, *args, **options):
        closed = close_expired_items()
        self.stdout.write(f"Closed {closed} item(s)")
```

- [ ] **Step 4: Run tests**

```bash
python manage.py test auction -v 2 > "$SCRATCH/t5.txt" 2>&1; tail -15 "$SCRATCH/t5.txt"
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add auction/services.py auction/management/ auction/tests/test_closing.py
git commit -S -m "feat: add winner selection with backup and closing command"
```

---

### Task 6: Bidder identity + web bid views + URLs (opus)

**Files:**
- Create: `auction/views.py`, `auction/urls.py`, `auction/forms.py`, `auction/tests/test_views.py`
- Create: `auction/templates/auction/item_detail.html` (minimal here; Task 7 styles it)
- Modify: `blowcomotion/urls.py` (mount before catch-all)

**Interfaces:**
- Consumes: `place_bid`/`BidError`/`close_expired_items`, `_validate_recaptcha` from `blowcomotion.views`, `normalize_phone`.
- Produces:
  - `resolve_bidder(request, auction) -> Bidder | None`: logged-in member match → signed cookie (`auction_bidder_<auction.pk>`, salt `"auction-bidder"`) → None
  - View `auction-item-detail` (`/auction/<int:auction_id>/item/<int:number>/`, GET): lazily calls `close_expired_items(auction)` when any expired unprocessed item exists; context: `item`, `bidder`, `bid_form`, `include_form_js=True`, `bids` (history, newest first)
  - View `auction-place-bid` (same path + `bid/`, POST): reCAPTCHA → resolve/register bidder → `place_bid` → PRG redirect with `django.contrib.messages`; sets the signed cookie for guests (30 days)
  - `BidderRegistrationForm` (name, email, phone, sms_opt_in) and `BidForm` (amount)
- Registration matching rule: if a guest submits email+phone matching an existing Bidder in this auction (case-insensitive email, normalized phone), reuse it (cookie reattach). Logged-in members: `get_or_create` by (auction, member), prefilled name/email/phone from the Member on create; the posted phone/sms_opt_in overwrite the prefill (their confirmation step).

- [ ] **Step 1: Write the failing tests**

`auction/tests/test_views.py`:

```python
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auction.models import Bidder
from auction.tests.test_models import make_auction, make_bidder, make_item
from blowcomotion.models import Member
from members.auth import create_member_user

User = get_user_model()


@patch("blowcomotion.views._validate_recaptcha", return_value=(True, None))
class BidViewTests(TestCase):
    def setUp(self):
        self.auction = make_auction()
        self.item = make_item(self.auction)
        self.detail_url = reverse("auction-item-detail", args=[self.auction.pk, self.item.number])
        self.bid_url = reverse("auction-place-bid", args=[self.auction.pk, self.item.number])

    def register_and_bid(self, amount="25", **extra):
        data = dict(
            name="Robin Player", email="robin@example.com", phone="512-555-1234",
            sms_opt_in="on", amount=amount,
        )
        data.update(extra)
        return self.client.post(self.bid_url, data)

    def test_detail_renders(self, _):
        response = self.client.get(self.detail_url)
        self.assertContains(response, "Yeti Cooler")
        self.assertContains(response, "data-recaptcha")

    def test_guest_first_bid_registers_and_sets_cookie(self, _):
        response = self.register_and_bid()
        self.assertRedirects(response, self.detail_url)
        bidder = Bidder.objects.get(auction=self.auction, email="robin@example.com")
        self.assertTrue(bidder.sms_opt_in)
        self.assertIn(f"auction_bidder_{self.auction.pk}", response.cookies)

    def test_cookie_bidder_skips_registration_fields(self, _):
        self.register_and_bid()
        response = self.client.post(self.bid_url, {"amount": "30"})
        self.assertRedirects(response, self.detail_url)
        self.assertEqual(self.item.bids.count(), 2)

    def test_same_email_phone_reattaches_existing_bidder(self, _):
        self.register_and_bid()
        self.client.cookies.clear()
        self.register_and_bid(amount="30")
        self.assertEqual(Bidder.objects.filter(auction=self.auction).count(), 1)

    def test_too_low_bid_shows_error(self, _):
        response = self.register_and_bid(amount="1")
        self.assertRedirects(response, self.detail_url)
        follow = self.client.get(self.detail_url)
        self.assertContains(follow, "at least $25")
        self.assertEqual(self.item.bids.count(), 0)

    def test_logged_in_member_prefills_and_links(self, _):
        member = Member.objects.create(
            first_name="Sam", last_name="Horn", email="sam@example.com", phone="512-555-8888"
        )
        user = create_member_user(member)
        user.set_password("Pass123!")
        user.save()
        self.client.login(username="sam@example.com", password="Pass123!")

        response = self.client.get(self.detail_url)
        self.assertContains(response, "sam@example.com")  # prefilled form

        self.client.post(self.bid_url, {
            "name": "Sam Horn", "email": "sam@example.com", "phone": "512-555-8888",
            "amount": "25",
        })
        bidder = Bidder.objects.get(auction=self.auction, member=member)
        self.assertEqual(self.item.bids.first().bidder, bidder)

    def test_expired_item_lazily_closed_on_view(self, _):
        self.item.close_time = timezone.now() - timedelta(minutes=1)
        self.item.save()
        make_bidder(self.auction)
        self.client.get(self.detail_url)
        self.item.refresh_from_db()
        self.assertIsNotNone(self.item.winner_notified_at)

    def test_recaptcha_failure_rejects(self, mock_captcha):
        mock_captcha.return_value = (False, "reCAPTCHA validation failed")
        response = self.register_and_bid()
        self.assertRedirects(response, self.detail_url)
        self.assertEqual(self.item.bids.count(), 0)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test auction.tests.test_views -v 2 > "$SCRATCH/t6.txt" 2>&1; tail -10 "$SCRATCH/t6.txt"
```
Expected: FAIL — `auction-item-detail` not a registered URL name.

- [ ] **Step 3: Implement**

`auction/forms.py`:

```python
from django import forms

from auction.models import normalize_phone


class BidderRegistrationForm(forms.Form):
    name = forms.CharField(max_length=255)
    email = forms.EmailField()
    phone = forms.CharField(
        max_length=30,
        help_text=(
            "Already registered on another device? Enter the same email and "
            "phone to continue bidding as the same person."
        ),
    )
    sms_opt_in = forms.BooleanField(
        required=False,
        label="Text me when I'm outbid (you can bid back by replying)",
    )

    def clean_phone(self):
        return normalize_phone(self.cleaned_data["phone"])


class BidForm(forms.Form):
    amount = forms.DecimalField(max_digits=8, decimal_places=2, min_value=0)
```

`auction/views.py`:

```python
import logging

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from auction.forms import BidderRegistrationForm, BidForm
from auction.models import Auction, AuctionItem, Bidder
from auction.services import BidError, close_expired_items, place_bid
from blowcomotion import views as blowcomotion_views

logger = logging.getLogger(__name__)

BIDDER_COOKIE_SALT = "auction-bidder"
BIDDER_COOKIE_MAX_AGE = 60 * 60 * 24 * 30


def _cookie_name(auction):
    return f"auction_bidder_{auction.pk}"


def resolve_bidder(request, auction):
    if request.user.is_authenticated and hasattr(request.user, "member"):
        bidder = auction.bidders.filter(member=request.user.member).first()
        if bidder:
            return bidder
    try:
        bidder_id = request.get_signed_cookie(
            _cookie_name(auction), default=None, salt=BIDDER_COOKIE_SALT
        )
    except Exception:
        bidder_id = None
    if bidder_id:
        return auction.bidders.filter(pk=bidder_id).first()
    return None


def _lazy_close(auction):
    from django.db.models import Q
    from django.utils import timezone

    now = timezone.now()
    pending = auction.items.filter(winner_notified_at__isnull=True).filter(
        Q(close_time__lte=now) | Q(close_time__isnull=True, auction__close_time__lte=now)
    )
    if pending.exists():
        close_expired_items(auction)


def _registration_initial(request):
    if request.user.is_authenticated and hasattr(request.user, "member"):
        member = request.user.member
        return {"name": member.full_name, "email": member.email, "phone": member.phone or ""}
    return {}


def item_detail(request, auction_id, number):
    auction = get_object_or_404(Auction, pk=auction_id)
    _lazy_close(auction)
    item = get_object_or_404(
        AuctionItem.objects.select_related("auction"), auction=auction, number=number
    )
    bidder = resolve_bidder(request, auction)
    return render(request, "auction/item_detail.html", {
        "auction": auction,
        "item": item,
        "bidder": bidder,
        "bids": item.bids.select_related("bidder").order_by("-amount"),
        "registration_form": BidderRegistrationForm(initial=_registration_initial(request)),
        "bid_form": BidForm(),
        "include_form_js": True,
    })


def _get_or_register_bidder(request, auction):
    """Returns (bidder, error_message)."""
    bidder = resolve_bidder(request, auction)
    if bidder:
        return bidder, None
    form = BidderRegistrationForm(request.POST)
    if not form.is_valid():
        return None, "; ".join(f"{f}: {e[0]}" for f, e in form.errors.items())
    data = form.cleaned_data
    member = request.user.member if (
        request.user.is_authenticated and hasattr(request.user, "member")
    ) else None
    if member:
        bidder, created = Bidder.objects.get_or_create(
            auction=auction, member=member,
            defaults=dict(name=data["name"], email=data["email"],
                          phone=data["phone"], sms_opt_in=data["sms_opt_in"]),
        )
        if not created:
            return bidder, None
    else:
        bidder = Bidder.objects.filter(
            auction=auction, email__iexact=data["email"], phone=data["phone"]
        ).first()
        if not bidder:
            try:
                bidder = Bidder.objects.create(
                    auction=auction, name=data["name"], email=data["email"],
                    phone=data["phone"], sms_opt_in=data["sms_opt_in"],
                )
            except Exception:
                return None, (
                    "That email or phone is already registered in this auction. "
                    "Enter the exact same email AND phone you registered with."
                )
    return bidder, None


@require_POST
def place_bid_view(request, auction_id, number):
    auction = get_object_or_404(Auction, pk=auction_id)
    item = get_object_or_404(AuctionItem, auction=auction, number=number)
    detail = redirect("auction-item-detail", auction_id=auction.pk, number=item.number)

    is_valid, error = blowcomotion_views._validate_recaptcha(request)
    if not is_valid:
        messages.error(request, error or "reCAPTCHA validation failed. Please try again.")
        return detail

    bidder, reg_error = _get_or_register_bidder(request, auction)
    if reg_error:
        messages.error(request, reg_error)
        return detail

    bid_form = BidForm(request.POST)
    if not bid_form.is_valid():
        messages.error(request, "Enter a valid bid amount.")
        return detail

    try:
        bid = place_bid(item.pk, bidder, bid_form.cleaned_data["amount"])
    except BidError as exc:
        messages.error(request, str(exc))
        return detail

    messages.success(request, f"You're the top bid on #{item.number} {item.title} at ${bid.amount}!")
    if not bidder.member_id:
        detail.set_signed_cookie(
            _cookie_name(auction), bidder.pk,
            salt=BIDDER_COOKIE_SALT, max_age=BIDDER_COOKIE_MAX_AGE, httponly=True, samesite="Lax",
        )
    return detail
```

Note the tests patch `blowcomotion.views._validate_recaptcha`, so views must call it as `blowcomotion_views._validate_recaptcha(...)` (module attribute), not import the name directly.

`auction/urls.py`:

```python
from django.urls import path

from auction import views

urlpatterns = [
    path("<int:auction_id>/item/<int:number>/", views.item_detail, name="auction-item-detail"),
    path("<int:auction_id>/item/<int:number>/bid/", views.place_bid_view, name="auction-place-bid"),
]
```

In `blowcomotion/urls.py` add after the `path("attendance/", ...)` line:

```python
    path("auction/", include("auction.urls")),
```

`auction/templates/auction/item_detail.html` (minimal; Task 7 finishes styling):

```html
{% extends "base.html" %}
{% block content %}
<div class="container py-4">
  {% for message in messages %}<div class="alert alert-{{ message.tags }}">{{ message }}</div>{% endfor %}
  <h1>#{{ item.number }} {{ item.title }}</h1>
  <p>{{ item.description|linebreaks }}</p>
  <p>Current bid: ${{ item.top_bid.amount|default:item.starting_bid }} — minimum next bid: ${{ item.minimum_bid }}</p>

  {% if item.is_open %}
  <form method="post" action="{% url 'auction-place-bid' auction.pk item.number %}" data-recaptcha>
    {% csrf_token %}
    {% if not bidder %}
      <p><a href="/member/login/?next={{ request.path|urlencode }}">Band member? Log in to skip this form.</a></p>
      {{ registration_form.as_p }}
    {% else %}
      <p>Bidding as {{ bidder.display_name }}</p>
    {% endif %}
    {{ bid_form.as_p }}
    <button type="submit" class="site-btn">Place bid</button>
  </form>
  {% else %}
    <p>Bidding closed.{% if item.winning_bid %} Won by {{ item.winning_bid.bidder.display_name }} (${{ item.winning_bid.amount }}).{% endif %}</p>
  {% endif %}

  <h2>Bid history</h2>
  <ul>{% for bid in bids %}<li>${{ bid.amount }} — {{ bid.bidder.display_name }} ({{ bid.created_at }})</li>{% empty %}<li>No bids yet.</li>{% endfor %}</ul>
</div>
{% endblock %}
```

- [ ] **Step 4: Verify form.js handles `data-recaptcha` forms**

Read `blowcomotion/static/js/form.js`. Confirm forms matching `form[data-recaptcha]` get BOTH the disclosure notice AND the grecaptcha token submit handler. If only the notice is injected, extend the existing handler-attachment selector list to include `form[data-recaptcha]` (edit under `blowcomotion/static/`, do not add inline template handlers, do not run collectstatic).

- [ ] **Step 5: Run tests**

```bash
python manage.py test auction -v 2 > "$SCRATCH/t6.txt" 2>&1; tail -15 "$SCRATCH/t6.txt"
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add auction/ blowcomotion/urls.py blowcomotion/static/js/form.js
git commit -S -m "feat: add auction bidding views with guest and member identity"
```

---

### Task 7: AuctionBlock, grid partial, polling + refresh, page wiring (sonnet)

**Files:**
- Create: `auction/blocks.py`, `auction/templates/auction/blocks/auction_block.html`, `auction/templates/auction/_grid.html`, `auction/tests/test_block.py`
- Modify: `auction/views.py` + `auction/urls.py` (grid partial endpoint), `blowcomotion/blocks/__init__.py` (re-export), `blowcomotion/models/pages.py` (add block to `BlankCanvasPage.body`), polish `auction/templates/auction/item_detail.html` (carousel)
- New migration: `blowcomotion` (StreamField change)

**Interfaces:**
- Consumes: Task 6 views/urls, Task 1 models.
- Produces: `AuctionBlock` (StructBlock: `auction` SnippetChooserBlock + optional `intro` RichTextBlock), URL `auction-grid` (`/auction/<int:auction_id>/grid/`, GET partial), block registered on `BlankCanvasPage.body` as `("auction", ...)`.

- [ ] **Step 1: Write the failing tests**

`auction/tests/test_block.py`:

```python
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auction.tests.test_models import make_auction, make_item


class GridPartialTests(TestCase):
    def setUp(self):
        self.auction = make_auction()
        self.open_item = make_item(self.auction)
        self.closed_item = make_item(
            self.auction, title="Gift Card", close_time=timezone.now() - timedelta(minutes=1)
        )

    def test_grid_splits_open_and_completed(self):
        response = self.client.get(reverse("auction-grid", args=[self.auction.pk]))
        self.assertContains(response, "Yeti Cooler")
        self.assertContains(response, "Gift Card")
        self.assertContains(response, "Completed")
        self.assertContains(response, "Last refreshed")

    def test_blank_canvas_page_offers_auction_block(self):
        from blowcomotion.models.pages import BlankCanvasPage

        body_field = BlankCanvasPage._meta.get_field("body")
        self.assertIn("auction", body_field.stream_block.child_blocks)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test auction.tests.test_block -v 2 > "$SCRATCH/t7.txt" 2>&1; tail -10 "$SCRATCH/t7.txt"
```
Expected: FAIL — no `auction-grid` URL.

- [ ] **Step 3: Implement**

`auction/blocks.py`:

```python
from wagtail import blocks
from wagtail.snippets.blocks import SnippetChooserBlock


class AuctionBlock(blocks.StructBlock):
    intro = blocks.RichTextBlock(required=False)
    auction = SnippetChooserBlock("auction.Auction")

    class Meta:
        template = "auction/blocks/auction_block.html"
        icon = "tag"
        label = "Auction"
```

Add to `auction/views.py`:

```python
def grid_partial(request, auction_id):
    auction = get_object_or_404(Auction, pk=auction_id)
    _lazy_close(auction)
    items = list(auction.items.prefetch_related("images", "bids"))
    return render(request, "auction/_grid.html", {
        "auction": auction,
        "open_items": [i for i in items if i.is_open],
        "closed_items": [i for i in items if not i.is_open],
    })
```

Add to `auction/urls.py`:

```python
    path("<int:auction_id>/grid/", views.grid_partial, name="auction-grid"),
```

`auction/templates/auction/blocks/auction_block.html`:

```html
{% if value.intro %}<div class="mb-3">{{ value.intro }}</div>{% endif %}
<div class="d-flex justify-content-end mb-2">
  <button type="button" class="site-btn"
          onclick="htmx.trigger('#auction-grid-{{ value.auction.pk }}', 'refreshAuction')">
    Refresh now
  </button>
</div>
<div id="auction-grid-{{ value.auction.pk }}"
     hx-get="{% url 'auction-grid' value.auction.pk %}"
     hx-trigger="every 60s, refreshAuction"
     hx-swap="innerHTML">
  {% include "auction/_grid.html" with auction=value.auction open_items=value.auction.open_items_list closed_items=value.auction.closed_items_list %}
</div>
```

For the initial (non-htmx) render the block template needs the same split the view computes — add two small helpers to `Auction` in `auction/models.py`:

```python
    def open_items_list(self):
        return [i for i in self.items.prefetch_related("images", "bids") if i.is_open]

    def closed_items_list(self):
        return [i for i in self.items.prefetch_related("images", "bids") if not i.is_open]
```

`auction/templates/auction/_grid.html`:

```html
{% load wagtailimages_tags %}
<div class="row g-3">
  {% for item in open_items %}
  <div class="col-6 col-md-4 col-lg-3">
    <div class="card h-100">
      {% with cover=item.images.first %}
        {% if cover %}{% image cover.image fill-400x300 class="card-img-top" %}{% endif %}
      {% endwith %}
      <div class="card-body">
        <h5 class="card-title">#{{ item.number }} {{ item.title }}</h5>
        <p class="card-text">
          Current: ${{ item.top_bid.amount|default:item.starting_bid }}<br>
          <small>{{ item.bids.count }} bid{{ item.bids.count|pluralize }} — closes {{ item.effective_close_time|date:"M j, g:i A" }}</small>
        </p>
        <a class="site-btn" href="{% url 'auction-item-detail' auction.pk item.number %}">View &amp; bid</a>
      </div>
    </div>
  </div>
  {% empty %}<p>No open items right now.</p>{% endfor %}
</div>

{% if closed_items %}
<h3 class="mt-4">Completed</h3>
<ul class="list-unstyled">
  {% for item in closed_items %}
  <li>
    #{{ item.number }} {{ item.title }} —
    {% if item.winning_bid %}won by {{ item.winning_bid.bidder.display_name }} (${{ item.winning_bid.amount }}){% else %}no bids{% endif %}
    <a href="{% url 'auction-item-detail' auction.pk item.number %}">details</a>
  </li>
  {% endfor %}
</ul>
{% endif %}
<p class="text-muted mt-2"><small>Last refreshed: {% now "g:i:s A" %} — updates automatically every minute.</small></p>
```

Re-export in `blowcomotion/blocks/__init__.py` (import at top, name in `__all__`):

```python
from auction.blocks import AuctionBlock
```

In `blowcomotion/models/pages.py` add to `BlankCanvasPage.body`'s list, alphabetically:

```python
            ("auction", blowcomotion_blocks.AuctionBlock()),
```

Item detail carousel — in `item_detail.html`, replace the single-image spot with a Bootstrap carousel when the item has multiple images:

```html
{% load wagtailimages_tags %}
{% with images=item.images.all %}
{% if images|length > 1 %}
<div id="item-carousel-{{ item.pk }}" class="carousel slide mb-3" data-bs-ride="carousel">
  <div class="carousel-inner">
    {% for img in images %}
    <div class="carousel-item {% if forloop.first %}active{% endif %}">{% image img.image width-800 class="d-block w-100" %}</div>
    {% endfor %}
  </div>
  <button class="carousel-control-prev" type="button" data-bs-target="#item-carousel-{{ item.pk }}" data-bs-slide="prev"><span class="carousel-control-prev-icon"></span></button>
  <button class="carousel-control-next" type="button" data-bs-target="#item-carousel-{{ item.pk }}" data-bs-slide="next"><span class="carousel-control-next-icon"></span></button>
</div>
{% elif images %}{% image images.0.image width-800 class="img-fluid mb-3" %}{% endif %}
{% endwith %}
```

Also add the same "Refresh now" + `hx-get` polling wrapper around the price/history section of the detail page pointing at a `hx-get="{{ request.path }}"` with `hx-select="#bid-state" hx-target="#bid-state"` (wrap current-bid + history in `<div id="bid-state">`), plus the "Last refreshed" line.

- [ ] **Step 4: Migration + tests**

```bash
python manage.py makemigrations blowcomotion > "$SCRATCH/t7-mig.txt" 2>&1; tail -5 "$SCRATCH/t7-mig.txt"
python manage.py test auction blowcomotion -v 1 > "$SCRATCH/t7.txt" 2>&1; tail -15 "$SCRATCH/t7.txt"
```
Expected: one `blowcomotion` migration (BlankCanvasPage body); all PASS.

- [ ] **Step 5: Commit**

```bash
git add auction/ blowcomotion/blocks/__init__.py blowcomotion/models/pages.py blowcomotion/migrations/
git commit -S -m "feat: add AuctionBlock with live grid on CMS pages"
```

---

### Task 8: Twilio inbound SMS webhook (opus)

**Files:**
- Create: `auction/sms.py`, `auction/tests/test_sms.py`
- Modify: `auction/urls.py`

**Interfaces:**
- Consumes: `place_bid`/`BidError`, models, `item_url`.
- Produces: POST `/auction/sms/` (name `auction-sms-webhook`, csrf-exempt). Validates `X-Twilio-Signature` with `twilio.request_validator.RequestValidator(TWILIO_AUTH_TOKEN)` against `request.build_absolute_uri()` + POST params; invalid → 403. When `TWILIO_AUTH_TOKEN` unset: allowed only when `settings.DEBUG`, else 403. Response: TwiML `MessagingResponse` XML. Commands: `BID <item#> <amount>` (case-insensitive, optional `#`/`$`), anything else → help text.

- [ ] **Step 1: Write the failing tests**

`auction/tests/test_sms.py`:

```python
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from auction.tests.test_models import make_auction, make_bidder, make_item


class SmsWebhookTests(TestCase):
    def setUp(self):
        self.auction = make_auction()
        self.item = make_item(self.auction)  # number 1, starting 25
        self.bidder = make_bidder(self.auction)  # +15125551234
        self.url = reverse("auction-sms-webhook")

    def sms(self, body, from_="+15125551234"):
        return self.client.post(self.url, {"From": from_, "Body": body})

    def test_valid_bid_places_and_confirms(self):
        response = self.sms("BID 1 25")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "top bid")
        bid = self.item.bids.get()
        self.assertEqual((bid.amount, bid.source), (Decimal("25"), "sms"))

    def test_bid_with_symbols_and_case(self):
        response = self.sms("bid #1 $25")
        self.assertEqual(self.item.bids.count(), 1)

    def test_too_low_bid_explains_minimum(self):
        response = self.sms("BID 1 5")
        self.assertContains(response, "at least $25")
        self.assertEqual(self.item.bids.count(), 0)

    def test_unknown_item(self):
        response = self.sms("BID 99 25")
        self.assertContains(response, "No item #99")

    def test_unknown_number_prompts_registration(self):
        response = self.sms("BID 1 25", from_="+15129990000")
        self.assertContains(response, "register")
        self.assertEqual(self.item.bids.count(), 0)

    def test_help_and_garbage_get_usage(self):
        for body in ("HELP", "what is this"):
            response = self.sms(body)
            self.assertContains(response, "BID")

    @override_settings(DEBUG=False, TWILIO_AUTH_TOKEN="secret-token")
    def test_invalid_signature_rejected(self):
        response = self.sms("BID 1 25")  # no/garbage signature header
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.item.bids.count(), 0)

    @override_settings(DEBUG=False)
    def test_no_token_in_production_rejected(self):
        response = self.sms("BID 1 25")
        self.assertEqual(response.status_code, 403)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test auction.tests.test_sms -v 2 > "$SCRATCH/t8.txt" 2>&1; tail -10 "$SCRATCH/t8.txt"
```
Expected: FAIL — no `auction-sms-webhook` URL.

- [ ] **Step 3: Implement**

`auction/sms.py`:

```python
import logging
import re

from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from auction import notifications
from auction.models import AuctionItem, Bidder
from auction.services import BidError, place_bid

logger = logging.getLogger(__name__)

BID_RE = re.compile(r"^\s*bid\s+#?(\d+)\s+\$?(\d+(?:\.\d{1,2})?)\s*$", re.IGNORECASE)
USAGE = 'To bid, text: BID <item number> <amount> — for example "BID 12 60".'


def _signature_valid(request):
    token = getattr(settings, "TWILIO_AUTH_TOKEN", None)
    if not token:
        # Dev convenience only; production must have the token configured.
        return settings.DEBUG
    validator = RequestValidator(token)
    return validator.validate(
        request.build_absolute_uri(),
        request.POST.dict(),
        request.headers.get("X-Twilio-Signature", ""),
    )


def _twiml(text):
    response = MessagingResponse()
    response.message(text)
    return HttpResponse(str(response), content_type="text/xml")


def _handle_bid(bidder, item_number, amount):
    item = AuctionItem.objects.filter(auction=bidder.auction, number=item_number).first()
    if item is None:
        return f"No item #{item_number} in {bidder.auction.name}. {USAGE}"
    try:
        bid = place_bid(item.pk, bidder, amount, source="sms")
    except BidError as exc:
        return str(exc)
    return (
        f"You're the top bid on #{item.number} {item.title} at ${bid.amount}! "
        f"{notifications.item_url(item)}"
    )


@csrf_exempt
@require_POST
def sms_webhook(request):
    if not _signature_valid(request):
        logger.warning("Rejected SMS webhook call with invalid signature")
        return HttpResponseForbidden()

    from_number = request.POST.get("From", "")
    body = request.POST.get("Body", "")

    bidder = Bidder.objects.filter(phone=from_number).order_by("-created_at").first()
    if bidder is None:
        return _twiml(
            "We don't recognize this number. Place your first bid on the auction "
            "page to register, then you can bid by text."
        )

    match = BID_RE.match(body)
    if match:
        from decimal import Decimal

        return _twiml(_handle_bid(bidder, int(match.group(1)), Decimal(match.group(2))))
    return _twiml(USAGE)
```

Add to `auction/urls.py`:

```python
from auction import sms
...
    path("sms/", sms.sms_webhook, name="auction-sms-webhook"),
```

- [ ] **Step 4: Run tests**

```bash
python manage.py test auction -v 1 > "$SCRATCH/t8.txt" 2>&1; tail -15 "$SCRATCH/t8.txt"
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add auction/sms.py auction/urls.py auction/tests/test_sms.py
git commit -S -m "feat: add Twilio inbound SMS bidding webhook"
```

---

### Task 9: Auctioneer manage dashboard + promote backup (sonnet)

**Files:**
- Create: `auction/templates/auction/manage.html`, `auction/tests/test_manage.py`
- Modify: `auction/views.py`, `auction/urls.py`, `auction/services.py`

**Interfaces:**
- Consumes: role perms from Task 2 (`auction.change_auctionitem`), `notify_winner`.
- Produces: `promote_backup(item) -> None` in services (swaps `winning_bid`←`backup_bid`, clears backup, re-stamps `winner_notified_at`, queues `notify_winner`); views `auction-manage` (GET `/auction/manage/`) and `auction-promote` (POST `/auction/manage/item/<int:pk>/promote/`), both `@login_required` + `@permission_required("auction.change_auctionitem", raise_exception=True)`.

- [ ] **Step 1: Write the failing tests**

`auction/tests/test_manage.py`:

```python
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auction.models import Bid
from auction.services import close_expired_items
from auction.tests.test_models import make_auction, make_bidder, make_item

User = get_user_model()


class ManageViewTests(TestCase):
    def setUp(self):
        self.auction = make_auction(close_time=timezone.now() - timedelta(minutes=1))
        self.item = make_item(self.auction)
        self.alice = make_bidder(self.auction)
        self.bob = make_bidder(self.auction, name="Bob Jones", email="bob@example.com", phone="512-555-9999")
        Bid.objects.create(item=self.item, bidder=self.alice, amount=Decimal("30"))
        Bid.objects.create(item=self.item, bidder=self.bob, amount=Decimal("25"))
        with patch("auction.notifications.notify_winner"), patch(
            "auction.notifications.send_auction_summary"
        ):
            with self.captureOnCommitCallbacks(execute=True):
                close_expired_items()
        self.item.refresh_from_db()

        self.auctioneer = User.objects.create_user(username="beej", password="Pass123!")
        self.auctioneer.user_permissions.add(
            Permission.objects.get(codename="change_auctionitem")
        )

    def test_anonymous_denied(self):
        response = self.client.get(reverse("auction-manage"))
        self.assertEqual(response.status_code, 302)  # to login

    def test_auctioneer_sees_winner_and_backup(self):
        self.client.login(username="beej", password="Pass123!")
        response = self.client.get(reverse("auction-manage"))
        self.assertContains(response, "Robin P.")
        self.assertContains(response, "Bob J.")
        self.assertContains(response, "Promote")

    @patch("auction.notifications.notify_winner")
    def test_promote_swaps_and_notifies(self, mock_notify):
        self.client.login(username="beej", password="Pass123!")
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("auction-promote", args=[self.item.pk]))
        self.assertRedirects(response, reverse("auction-manage"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.winning_bid.bidder, self.bob)
        self.assertIsNone(self.item.backup_bid)
        mock_notify.assert_called_once_with(self.item)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test auction.tests.test_manage -v 2 > "$SCRATCH/t9.txt" 2>&1; tail -10 "$SCRATCH/t9.txt"
```
Expected: FAIL — no `auction-manage` URL.

- [ ] **Step 3: Implement**

Append to `auction/services.py`:

```python
def promote_backup(item):
    """Auctioneer action: the winner flaked, promote the backup and notify them."""
    from auction import notifications

    with transaction.atomic():
        item = AuctionItem.objects.select_for_update().get(pk=item.pk)
        if not item.backup_bid:
            raise BidError("This item has no backup bidder to promote.")
        item.winning_bid = item.backup_bid
        item.backup_bid = None
        item.winner_notified_at = timezone.now()
        item.save(update_fields=["winning_bid", "backup_bid", "winner_notified_at"])
        transaction.on_commit(lambda: notifications.notify_winner(item))
```

Add to `auction/views.py`:

```python
from django.contrib.auth.decorators import login_required, permission_required

from auction.services import promote_backup  # extend the existing services import


@login_required
@permission_required("auction.change_auctionitem", raise_exception=True)
def manage(request):
    auctions = Auction.objects.prefetch_related(
        "items__winning_bid__bidder", "items__backup_bid__bidder", "items__bids"
    )
    return render(request, "auction/manage.html", {"auctions": auctions})


@login_required
@permission_required("auction.change_auctionitem", raise_exception=True)
@require_POST
def promote(request, pk):
    item = get_object_or_404(AuctionItem, pk=pk)
    try:
        promote_backup(item)
        messages.success(request, f"Backup promoted to winner on #{item.number} {item.title}.")
    except BidError as exc:
        messages.error(request, str(exc))
    return redirect("auction-manage")
```

Add to `auction/urls.py`:

```python
    path("manage/", views.manage, name="auction-manage"),
    path("manage/item/<int:pk>/promote/", views.promote, name="auction-promote"),
```

`auction/templates/auction/manage.html`:

```html
{% extends "base.html" %}
{% block content %}
<div class="container py-4">
  <h1>Auction management</h1>
  {% for message in messages %}<div class="alert alert-{{ message.tags }}">{{ message }}</div>{% endfor %}
  {% for auction in auctions %}
  <h2>{{ auction.name }}</h2>
  <div class="table-responsive"><table class="table">
    <thead><tr><th>Item</th><th>Bids</th><th>Winner</th><th>Backup</th><th></th></tr></thead>
    <tbody>
      {% for item in auction.items.all %}
      <tr>
        <td>#{{ item.number }} {{ item.title }}</td>
        <td>{{ item.bids.count }}</td>
        <td>{% if item.winning_bid %}{{ item.winning_bid.bidder.display_name }} (${{ item.winning_bid.amount }}){% elif item.winner_notified_at %}no bids{% else %}open{% endif %}</td>
        <td>{% if item.backup_bid %}{{ item.backup_bid.bidder.display_name }} (${{ item.backup_bid.amount }}){% endif %}</td>
        <td>
          {% if item.backup_bid %}
          <form method="post" action="{% url 'auction-promote' item.pk %}" onsubmit="return confirm('Promote backup to winner? They will be notified.')">
            {% csrf_token %}<button type="submit" class="site-btn">Promote backup</button>
          </form>
          {% endif %}
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table></div>
  {% endfor %}
</div>
{% endblock %}
```

- [ ] **Step 4: Run tests**

```bash
python manage.py test auction -v 1 > "$SCRATCH/t9.txt" 2>&1; tail -15 "$SCRATCH/t9.txt"
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add auction/
git commit -S -m "feat: add auctioneer manage dashboard with backup promotion"
```

---

### Task 10: Wagtail admin snippets (sonnet)

**Files:**
- Create: `auction/wagtail_hooks.py`, `auction/tests/test_admin.py`

**Interfaces:**
- Consumes: models; Wagtail `SnippetViewSet`/`SnippetViewSetGroup` (see `blowcomotion/snippet_viewsets.py` for house style).
- Produces: "Auction" admin menu group with Auctions (items editable via chooser to their own list), Auction Items (with inline image panel), Bidders (read-oriented), Bids (read-oriented).

- [ ] **Step 1: Write the failing test**

`auction/tests/test_admin.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python manage.py test auction.tests.test_admin -v 2 > "$SCRATCH/t10.txt" 2>&1; tail -10 "$SCRATCH/t10.txt"
```
Expected: FAIL — 404 (snippets not registered).

- [ ] **Step 3: Implement**

`auction/wagtail_hooks.py`:

```python
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from auction.models import Auction, AuctionItem, Bid, Bidder


class AuctionViewSet(SnippetViewSet):
    model = Auction
    menu_label = "Auctions"
    icon = "tag"
    list_display = ["name", "close_time", "soft_close_enabled"]
    panels = [
        FieldPanel("name"),
        FieldPanel("description"),
        FieldPanel("close_time"),
        FieldPanel("soft_close_enabled"),
        FieldPanel("soft_close_minutes"),
        FieldPanel("payment_instructions"),
    ]


class AuctionItemViewSet(SnippetViewSet):
    model = AuctionItem
    menu_label = "Items"
    icon = "clipboard-list"
    list_display = ["number", "title", "auction", "starting_bid"]
    list_filter = ["auction"]
    panels = [
        FieldPanel("auction"),
        FieldPanel("number", help_text="Leave blank to auto-assign the next number."),
        FieldPanel("title"),
        FieldPanel("description"),
        FieldPanel("starting_bid"),
        FieldPanel("bid_increment"),
        FieldPanel("close_time"),
        InlinePanel("images", label="Images (first one is the cover)"),
    ]


class BidderViewSet(SnippetViewSet):
    model = Bidder
    menu_label = "Bidders"
    icon = "user"
    list_display = ["name", "email", "phone", "sms_opt_in", "auction"]
    list_filter = ["auction"]


class BidViewSet(SnippetViewSet):
    model = Bid
    menu_label = "Bids"
    icon = "form"
    list_display = ["item", "bidder", "amount", "source", "created_at"]
    list_filter = ["item__auction", "source"]


class AuctionGroup(SnippetViewSetGroup):
    menu_label = "Auction"
    menu_icon = "tag"
    items = (AuctionViewSet, AuctionItemViewSet, BidderViewSet, BidViewSet)


register_snippet(AuctionGroup)
```

Note: `number` on `AuctionItem` is nullable specifically so the admin form can leave it blank and `save()` auto-assigns. If Wagtail's form makes the panel required, add `blank=True` is already set — verify by loading the create form in the test.

- [ ] **Step 4: Run tests**

```bash
python manage.py test auction -v 1 > "$SCRATCH/t10.txt" 2>&1; tail -15 "$SCRATCH/t10.txt"
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add auction/wagtail_hooks.py auction/tests/test_admin.py
git commit -S -m "feat: register auction snippets in Wagtail admin"
```

---

### Task 11: Demo seed command (haiku)

**Files:**
- Create: `auction/management/commands/seed_auction_demo.py`

**Interfaces:**
- Consumes: models. Idempotent by auction name.

- [ ] **Step 1: Implement (no TDD — dev-only utility, verify by running)**

```python
"""
Seed a demo auction with items modeled on the fall-2025 fundraiser merchants
(per Beej's request in issue #116). Safe to re-run: skips if the demo auction
already exists. Dev only.
"""
from datetime import timedelta
from decimal import Decimal

from wagtail.images import get_image_model

from django.core.management.base import BaseCommand
from django.utils import timezone

from auction.models import Auction, AuctionItem, AuctionItemImage

ITEMS = [
    ("Yeti Cooler", Decimal("50"), Decimal("5")),
    ("Restaurant Gift Card - Dinner for Two", Decimal("25"), Decimal("5")),
    ("Local Brewery Tour + Tasting", Decimal("30"), Decimal("5")),
    ("Yoga Studio 10-Class Pass", Decimal("40"), Decimal("5")),
    ("Coffee Shop Gift Basket", Decimal("15"), Decimal("2")),
    ("Record Store Vinyl Bundle", Decimal("20"), Decimal("2")),
    ("Tattoo Shop Gift Certificate", Decimal("60"), Decimal("10")),
]


class Command(BaseCommand):
    help = "Create a demo auction with sample items for development/testing"

    def handle(self, *args, **options):
        name = "Demo Fall Fundraiser Auction"
        if Auction.objects.filter(name=name).exists():
            self.stdout.write("Demo auction already exists, skipping")
            return
        auction = Auction.objects.create(
            name=name,
            description="Demo data seeded for development.",
            close_time=timezone.now() + timedelta(days=14),
            soft_close_enabled=True,
            payment_instructions="Pay at the merch table after the show.",
        )
        Image = get_image_model()
        for title, start, increment in ITEMS:
            item = AuctionItem.objects.create(
                auction=auction, title=title, starting_bid=start, bid_increment=increment
            )
            image = Image.objects.filter(title__icontains=title.split()[0]).first()
            if image:
                AuctionItemImage.objects.create(item=item, image=image)
        self.stdout.write(self.style.SUCCESS(f"Seeded '{name}' with {len(ITEMS)} items"))
```

- [ ] **Step 2: Verify**

```bash
python manage.py seed_auction_demo > "$SCRATCH/t11.txt" 2>&1; tail -3 "$SCRATCH/t11.txt"
python manage.py seed_auction_demo >> "$SCRATCH/t11.txt" 2>&1; tail -2 "$SCRATCH/t11.txt"
```
Expected: first run seeds 7 items; second run skips.

- [ ] **Step 3: Commit**

```bash
git add auction/management/commands/seed_auction_demo.py
git commit -S -m "chore: add demo auction seed command"
```

---

### Task 12: Integration pass, docs, PR (main session — not a subagent)

- [ ] **Step 1: Full test suite**

```bash
python manage.py test > "$SCRATCH/t12-full.txt" 2>&1; tail -20 "$SCRATCH/t12-full.txt"
```
Expected: entire project PASS (not just `auction`).

- [ ] **Step 2: Manual smoke test** (superpowers:verification-before-completion + `/verify`)

Run `python manage.py migrate && python manage.py setup_roles && python manage.py seed_auction_demo && python manage.py runserver`, then drive: grid via a BlankCanvasPage with the auction block (create in Wagtail admin), guest bid, second-account outbid (check console email), SMS webhook via `curl -X POST localhost:8000/auction/sms/ -d "From=+15125551234&Body=BID 1 60"`, `close_auction_items` after setting `close_time` in the past, promote flow at `/auction/manage/`.

- [ ] **Step 3: Update CLAUDE.md** — add an "Auction app" paragraph under Architecture overview: own models/migrations, Twilio settings (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` in `local.py`, absent → SMS skipped), Auctioneer role, hourly `close_auction_items` cron, webhook URL to configure in the Twilio console (`https://<host>/auction/sms/`).

- [ ] **Step 4: PR**

```bash
git push -u origin feature/issue-116-auction-app
gh pr create --base development --title "Silent auction app with SMS bidding (issue #116)" --body-file "$SCRATCH/pr-body.md"
```
PR body: summary per spec section, test plan, ops notes (A2P 10DLC registration must be started now; add hourly cron on PythonAnywhere; set Twilio webhook; page privacy = Auctioneer group until launch). No emojis, no AI sign-off.

---

## Post-merge ops checklist (humans, not code)

1. Buy Twilio number; start A2P 10DLC or toll-free verification immediately.
2. Add `TWILIO_*` settings to production `local.py`; set the number's inbound webhook to `https://www.blowcomotion.org/auction/sms/` (HTTP POST).
3. `ssh pythonanywhere`: run `migrate`, `setup_roles`, add hourly `close_auction_items` scheduled task.
4. Create the auction CMS page with the Auction block; set page privacy to the Auctioneer group until launch.
5. Add Beej/Charlene to the Auctioneer group.
