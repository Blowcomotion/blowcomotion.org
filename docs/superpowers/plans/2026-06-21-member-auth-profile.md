# Member Authentication & Profile Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Django User accounts linked to existing Member records, secure authentication flows (login/logout/set-password/reset/get-access), self-service profile editing, a bulk-invite management command, and a member portal with a stubbed requests dashboard.

**Architecture:** Django's built-in auth views (LoginView, PasswordResetView, etc.) are subclassed with custom templates. A `OneToOneField(User)` on `Member` links the two models. `blowcomotion/member_auth.py` holds pure helper functions; `blowcomotion/member_views.py` holds all views; `blowcomotion/member_urls.py` wires them up and is registered before `wagtail_urls`.

**Tech Stack:** Django 6.0.6, Wagtail 7.4.2, django-axes (login rate-limiting), django-ratelimit (token/form rate-limiting), argon2-cffi (Argon2 password hashing), Bootstrap (already included).

## Global Constraints

- Django 6.0.6, Wagtail 7.4.2 — no upgrades or downgrades.
- `argon2-cffi`, `django-axes`, `django-ratelimit` — pin to no specific version; install latest compatible.
- `FROM_EMAIL = settings.FROM_EMAIL` — already defined in `base.py`; use it for all outbound email.
- reCAPTCHA v3 — use existing `_validate_recaptcha(request)` from `blowcomotion/views.py`; pass `include_form_js=True` in every render context that shows a form.
- Honeypot field — `<input type="text" name="best_color" class="best-color" style="display:none;">` on every public form; reject POST if `request.POST.get("best_color")` is truthy.
- All member templates extend `base.html` (same pattern as `member_signup_success.html`).
- `Member.email` is the source of truth; `User.email` and `User.username` are derived.
- Tests in `blowcomotion/tests/test_*.py`; follow patterns in `test_member_model.py`.
- Frequent commits — one commit per task at minimum.
- `sync_go3=False` on any `Member.save()` call initiated from auth code (avoids needless GO3 API calls).

---

## File Map

### New files
| File | Responsibility |
|---|---|
| `blowcomotion/member_auth.py` | `create_member_user`, `send_set_password_email`, `send_email_change_confirmation` |
| `blowcomotion/member_views.py` | All member views (auth + portal) |
| `blowcomotion/member_forms.py` | `GetAccessForm`, `MemberProfileForm` |
| `blowcomotion/member_urls.py` | `/member/` URL patterns |
| `blowcomotion/middleware.py` | `MemberIdleLogoutMiddleware` |
| `blowcomotion/management/commands/invite_members.py` | Bulk invite command |
| `blowcomotion/templates/member/login.html` | Login form |
| `blowcomotion/templates/member/set_password.html` | Set/claim password form |
| `blowcomotion/templates/member/get_access.html` | Get-access email form |
| `blowcomotion/templates/member/password_reset.html` | Password reset request form |
| `blowcomotion/templates/member/password_reset_done.html` | "Check your email" page |
| `blowcomotion/templates/member/password_reset_confirm.html` | New password entry form |
| `blowcomotion/templates/member/password_reset_complete.html` | "Password changed" page |
| `blowcomotion/templates/member/portal_base.html` | Member portal base (nav + layout) |
| `blowcomotion/templates/member/profile.html` | Profile edit page |
| `blowcomotion/templates/member/requests.html` | My Requests stub page |
| `blowcomotion/templates/emails/set_password.txt` | Set-password email body |
| `blowcomotion/templates/emails/email_change_confirm.txt` | Email-change confirmation body |
| `blowcomotion/tests/test_member_auth_helpers.py` | Tests for models + helpers |
| `blowcomotion/tests/test_member_auth_views.py` | Tests for auth views |
| `blowcomotion/tests/test_member_portal.py` | Tests for portal views |
| `blowcomotion/tests/test_invite_members_command.py` | Tests for invite_members command |
| `blowcomotion/tests/test_member_middleware.py` | Tests for idle-logout middleware |

### Modified files
| File | Change |
|---|---|
| `requirements.txt` | Add `argon2-cffi`, `django-axes`, `django-ratelimit` |
| `blowcomotion/settings/base.py` | PASSWORD_HASHERS, AXES_*, AUTHENTICATION_BACKENDS, LOGIN_URL, LOGIN_REDIRECT_URL, LOGOUT_REDIRECT_URL, session settings, add `axes` to INSTALLED_APPS and MIDDLEWARE |
| `blowcomotion/settings/production.py` | `SESSION_COOKIE_SECURE = True` |
| `blowcomotion/models.py` | `PasswordSetToken`, `EmailChangeToken` models; `user`, `pending_email`, `notify_*` fields on `Member`; email drift guard in `Member.save()` |
| `blowcomotion/urls.py` | Include `member_urls` before `wagtail_urls` |
| `blowcomotion/views.py` | Call `create_member_user` + `send_set_password_email` at end of `_process_member_signup` |
| `blowcomotion/templates/header.html` | Login/logout/"My Profile" links |

---

## Execution Order

```
Wave 1 (sequential):   Task 1 — Dependencies & Settings
Wave 2 (sequential):   Task 2 — Data Models
Wave 3 (sequential):   Task 3 — Core Auth Helpers
Wave 4 (parallel):     Tasks 4, 5, 6, 7, 8
Wave 5 (parallel):     Tasks 9, 10
```

---

### Task 1: Dependencies & Settings

**Files:**
- Modify: `requirements.txt`
- Modify: `blowcomotion/settings/base.py`
- Modify: `blowcomotion/settings/production.py`

**Interfaces:**
- Produces: `settings.LOGIN_URL = "/member/login/"`, `settings.LOGIN_REDIRECT_URL = "/member/profile/"`, `settings.LOGOUT_REDIRECT_URL = "/"`, `settings.MEMBER_IDLE_TIMEOUT = 3600`, `axes` in INSTALLED_APPS

- [ ] **Step 1: Install new packages**

```bash
pip install argon2-cffi django-axes django-ratelimit
```

- [ ] **Step 2: Update requirements.txt**

Add these three lines to `requirements.txt`:
```
argon2-cffi
django-axes
django-ratelimit
```

- [ ] **Step 3: Update settings/base.py — PASSWORD_HASHERS**

After the `AUTH_PASSWORD_VALIDATORS` block (around line 123), add:

```python
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]
```

- [ ] **Step 4: Update settings/base.py — INSTALLED_APPS**

Add `"axes"` to `INSTALLED_APPS` (anywhere after `"django.contrib.auth"`):

```python
INSTALLED_APPS = [
    # ... existing apps ...
    "axes",
    # ... rest of apps ...
]
```

- [ ] **Step 5: Update settings/base.py — MIDDLEWARE**

Add `"axes.middleware.AxesMiddleware"` immediately after `AuthenticationMiddleware`:

```python
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "axes.middleware.AxesMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
    "livereload.middleware.LiveReloadScript",
]
```

- [ ] **Step 6: Update settings/base.py — auth, session, and axes config**

After the `TIME_ZONE` block, add:

```python
# Member auth
LOGIN_URL = "/member/login/"
LOGIN_REDIRECT_URL = "/member/profile/"
LOGOUT_REDIRECT_URL = "/"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# django-axes: rate-limit login attempts
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1800  # seconds (30 minutes)
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_PARAMETERS = ["ip_address"]

# Session security
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
MEMBER_IDLE_TIMEOUT = 3600  # seconds (60 minutes); used by MemberIdleLogoutMiddleware
```

- [ ] **Step 7: Update settings/production.py — secure cookie**

Add before the `try` block:

```python
SESSION_COOKIE_SECURE = True
```

- [ ] **Step 8: Verify Django check passes**

```bash
python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 9: Commit**

```bash
git add requirements.txt blowcomotion/settings/base.py blowcomotion/settings/production.py
git commit -m "feat: add argon2, django-axes, django-ratelimit; configure auth settings"
```

---

### Task 2: Data Models

**Files:**
- Modify: `blowcomotion/models.py` (add fields to Member, add two new models, update Member.save())
- Test: `blowcomotion/tests/test_member_auth_helpers.py`

**Interfaces:**
- Produces:
  - `Member.user` — `OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, related_name="member")`
  - `Member.pending_email` — `EmailField(null=True, blank=True)`
  - `Member.notify_rental_updates`, `Member.notify_reminders`, `Member.notify_announcements` — `BooleanField(default=True)`
  - `PasswordSetToken` model with fields: `member` (FK), `uuid` (UUIDField), `created_at`, `used` (bool), `superseded` (bool)
  - `EmailChangeToken` model with fields: `member` (FK), `uuid` (UUIDField), `new_email`, `created_at`, `used` (bool)

- [ ] **Step 1: Write the failing tests**

Create `blowcomotion/tests/test_member_auth_helpers.py`:

```python
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from blowcomotion.models import EmailChangeToken, Member, PasswordSetToken, Section

User = get_user_model()


def make_member(**kwargs):
    defaults = dict(first_name="Jane", last_name="Player", email="jane@example.com")
    defaults.update(kwargs)
    return Member.objects.create(**defaults)


class MemberUserFieldTests(TestCase):
    def test_member_has_no_user_by_default(self):
        m = make_member()
        self.assertIsNone(m.user)

    def test_member_can_link_user(self):
        m = make_member()
        u = User.objects.create_user(username="jane@example.com", email="jane@example.com")
        m.user = u
        m.save(update_fields=["user"], sync_go3=False)
        m.refresh_from_db()
        self.assertEqual(m.user_id, u.pk)

    def test_notify_fields_default_true(self):
        m = make_member()
        self.assertTrue(m.notify_rental_updates)
        self.assertTrue(m.notify_reminders)
        self.assertTrue(m.notify_announcements)

    def test_pending_email_default_null(self):
        m = make_member()
        self.assertIsNone(m.pending_email)


class PasswordSetTokenTests(TestCase):
    def setUp(self):
        self.member = make_member()

    def test_token_created_with_defaults(self):
        token = PasswordSetToken.objects.create(member=self.member)
        self.assertFalse(token.used)
        self.assertFalse(token.superseded)
        self.assertIsNotNone(token.uuid)

    def test_token_uuid_is_unique(self):
        t1 = PasswordSetToken.objects.create(member=self.member)
        t2 = PasswordSetToken.objects.create(member=self.member)
        self.assertNotEqual(t1.uuid, t2.uuid)

    def test_used_token_can_be_marked(self):
        token = PasswordSetToken.objects.create(member=self.member)
        token.used = True
        token.save()
        token.refresh_from_db()
        self.assertTrue(token.used)

    def test_superseded_token_can_be_marked(self):
        token = PasswordSetToken.objects.create(member=self.member)
        token.superseded = True
        token.save()
        token.refresh_from_db()
        self.assertTrue(token.superseded)


class EmailChangeTokenTests(TestCase):
    def setUp(self):
        self.member = make_member()

    def test_token_stores_new_email(self):
        token = EmailChangeToken.objects.create(
            member=self.member, new_email="new@example.com"
        )
        self.assertEqual(token.new_email, "new@example.com")
        self.assertFalse(token.used)

    def test_token_uuid_is_unique(self):
        t1 = EmailChangeToken.objects.create(member=self.member, new_email="a@example.com")
        t2 = EmailChangeToken.objects.create(member=self.member, new_email="b@example.com")
        self.assertNotEqual(t1.uuid, t2.uuid)


class MemberSaveEmailDriftTests(TestCase):
    def test_admin_email_change_syncs_user(self):
        member = make_member(email="old@example.com")
        user = User.objects.create_user(
            username="old@example.com", email="old@example.com"
        )
        member.user = user
        member.save(update_fields=["user"], sync_go3=False)

        member.email = "new@example.com"
        member.save(update_fields=["email"], sync_go3=False)

        user.refresh_from_db()
        self.assertEqual(user.email, "new@example.com")
        self.assertEqual(user.username, "new@example.com")

    def test_no_user_linked_no_error(self):
        member = make_member(email="solo@example.com")
        member.email = "changed@example.com"
        member.save(update_fields=["email"], sync_go3=False)  # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test blowcomotion.tests.test_member_auth_helpers -v 2
```

Expected: Errors like `ImportError: cannot import name 'PasswordSetToken'` or `AttributeError: Member has no field 'user'`.

- [ ] **Step 3: Add fields to Member model**

In `blowcomotion/models.py`, add these imports at the top (after existing imports):

```python
import uuid as uuid_module

from django.conf import settings
```

In the `Member` model, add the new fields after `inspired_by` (around line 633):

```python
    # Auth
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="member",
    )
    pending_email = models.EmailField(null=True, blank=True)

    # Notification preferences
    notify_rental_updates = models.BooleanField(default=True)
    notify_reminders = models.BooleanField(default=True)
    notify_announcements = models.BooleanField(default=True)
```

- [ ] **Step 4: Add PasswordSetToken and EmailChangeToken models**

After the `Member` class (before `CachedGig`, around line 955), add:

```python
class PasswordSetToken(models.Model):
    member = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name="set_password_tokens"
    )
    uuid = models.UUIDField(default=uuid_module.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)
    superseded = models.BooleanField(default=False)

    def __str__(self):
        return f"PasswordSetToken({self.member}, used={self.used})"


class EmailChangeToken(models.Model):
    member = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name="email_change_tokens"
    )
    uuid = models.UUIDField(default=uuid_module.uuid4, unique=True, editable=False)
    new_email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    def __str__(self):
        return f"EmailChangeToken({self.member} → {self.new_email})"
```

- [ ] **Step 5: Add email drift guard to Member.save()**

At the very end of `Member.save()`, just before `def __str__` (after line 949), add:

```python
        # Sync User.email and User.username if admin changed Member.email
        if self.user_id and (update_fields is None or "email" in update_fields):
            from django.contrib.auth import get_user_model as _get_user_model
            _User = _get_user_model()
            try:
                _user = _User.objects.get(pk=self.user_id)
                new_email = self.email or ""
                if _user.email != new_email or _user.username != new_email:
                    _user.email = new_email
                    _user.username = new_email
                    _user.save(update_fields=["email", "username"])
                    logger.info(f"Synced User email/username for member {self.pk}")
            except _User.DoesNotExist:
                pass
```

- [ ] **Step 6: Create and run migration**

```bash
python manage.py makemigrations blowcomotion --name member_auth_fields
python manage.py migrate
```

Expected: new migration file created and applied successfully.

- [ ] **Step 7: Run tests**

```bash
python manage.py test blowcomotion.tests.test_member_auth_helpers -v 2
```

Expected: All tests PASS.

- [ ] **Step 8: Commit**

```bash
git add blowcomotion/models.py blowcomotion/migrations/ blowcomotion/tests/test_member_auth_helpers.py
git commit -m "feat: add Member.user, PasswordSetToken, EmailChangeToken models and email drift guard"
```

---

### Task 3: Core Auth Helpers

**Files:**
- Create: `blowcomotion/member_auth.py`
- Create: `blowcomotion/templates/emails/set_password.txt`
- Create: `blowcomotion/templates/emails/email_change_confirm.txt`
- Test: `blowcomotion/tests/test_member_auth_helpers.py` (extend existing file)

**Interfaces:**
- Produces:
  - `create_member_user(member: Member) -> User` — creates a Django User with unusable password linked to Member; returns existing User if already linked
  - `send_set_password_email(member: Member, request) -> None` — creates PasswordSetToken (superseding prior unused ones) and emails member the set-password link
  - `send_email_change_confirmation(member: Member, new_email: str, request) -> None` — creates EmailChangeToken and emails `new_email` the confirmation link; sets `member.pending_email`

- [ ] **Step 1: Add helper tests to test_member_auth_helpers.py**

Append to `blowcomotion/tests/test_member_auth_helpers.py`:

```python
from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings

from blowcomotion.member_auth import (
    create_member_user,
    send_email_change_confirmation,
    send_set_password_email,
)


class CreateMemberUserTests(TestCase):
    def setUp(self):
        self.member = make_member(email="test@example.com")

    def test_creates_user_with_unusable_password(self):
        user = create_member_user(self.member)
        self.assertFalse(user.has_usable_password())

    def test_sets_username_and_email_from_member_email(self):
        user = create_member_user(self.member)
        self.assertEqual(user.username, "test@example.com")
        self.assertEqual(user.email, "test@example.com")

    def test_links_user_to_member(self):
        user = create_member_user(self.member)
        self.member.refresh_from_db()
        self.assertEqual(self.member.user_id, user.pk)

    def test_returns_existing_user_if_already_linked(self):
        user1 = create_member_user(self.member)
        user2 = create_member_user(self.member)
        self.assertEqual(user1.pk, user2.pk)
        self.assertEqual(User.objects.filter(email="test@example.com").count(), 1)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FROM_EMAIL="noreply@blowcomotion.org",
)
class SendSetPasswordEmailTests(TestCase):
    def setUp(self):
        self.member = make_member(email="invite@example.com")
        create_member_user(self.member)
        self.factory = RequestFactory()

    def test_sends_email_to_member(self):
        from django.core import mail
        request = self.factory.get("/")
        request.META["SERVER_NAME"] = "testserver"
        request.META["SERVER_PORT"] = "80"
        send_set_password_email(self.member, request)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("invite@example.com", mail.outbox[0].to)

    def test_email_contains_set_password_link(self):
        from django.core import mail
        request = self.factory.get("/")
        request.META["SERVER_NAME"] = "testserver"
        request.META["SERVER_PORT"] = "80"
        send_set_password_email(self.member, request)
        self.assertIn("/member/set-password/", mail.outbox[0].body)

    def test_creates_password_set_token(self):
        request = self.factory.get("/")
        request.META["SERVER_NAME"] = "testserver"
        request.META["SERVER_PORT"] = "80"
        send_set_password_email(self.member, request)
        self.assertEqual(
            PasswordSetToken.objects.filter(member=self.member, used=False, superseded=False).count(), 1
        )

    def test_supersedes_prior_tokens(self):
        token_old = PasswordSetToken.objects.create(member=self.member)
        request = self.factory.get("/")
        request.META["SERVER_NAME"] = "testserver"
        request.META["SERVER_PORT"] = "80"
        send_set_password_email(self.member, request)
        token_old.refresh_from_db()
        self.assertTrue(token_old.superseded)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FROM_EMAIL="noreply@blowcomotion.org",
)
class SendEmailChangeConfirmationTests(TestCase):
    def setUp(self):
        self.member = make_member(email="original@example.com")
        self.factory = RequestFactory()

    def test_sends_email_to_new_address(self):
        from django.core import mail
        request = self.factory.get("/")
        request.META["SERVER_NAME"] = "testserver"
        request.META["SERVER_PORT"] = "80"
        send_email_change_confirmation(self.member, "newemail@example.com", request)
        self.assertIn("newemail@example.com", mail.outbox[0].to)

    def test_email_contains_confirm_link(self):
        from django.core import mail
        request = self.factory.get("/")
        request.META["SERVER_NAME"] = "testserver"
        request.META["SERVER_PORT"] = "80"
        send_email_change_confirmation(self.member, "newemail@example.com", request)
        self.assertIn("/member/confirm-email/", mail.outbox[0].body)

    def test_sets_pending_email_on_member(self):
        request = self.factory.get("/")
        request.META["SERVER_NAME"] = "testserver"
        request.META["SERVER_PORT"] = "80"
        send_email_change_confirmation(self.member, "newemail@example.com", request)
        self.member.refresh_from_db()
        self.assertEqual(self.member.pending_email, "newemail@example.com")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test blowcomotion.tests.test_member_auth_helpers.CreateMemberUserTests -v 2
```

Expected: `ImportError: cannot import name 'create_member_user' from 'blowcomotion.member_auth'`

- [ ] **Step 3: Create blowcomotion/member_auth.py**

```python
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
```

- [ ] **Step 4: Create email templates**

Create `blowcomotion/templates/emails/set_password.txt`:

```
Hi {{ member.full_name }},

Welcome to Blowcomotion — set your password to access your member profile.

Click the link below to set your password. This link expires in 24 hours and can only be used once.

{{ set_password_url }}

If you didn't request this, you can safely ignore this email.

Start Wearing Purple,
Blowcomotion
```

Create `blowcomotion/templates/emails/email_change_confirm.txt`:

```
Hi {{ member.full_name }},

You requested to change your Blowcomotion email address to {{ new_email }}.

Click the link below to confirm this change. This link expires in 24 hours.

{{ confirm_url }}

If you didn't request this change, please log in and check your account.

Start Wearing Purple,
Blowcomotion
```

- [ ] **Step 5: Run all helper tests**

```bash
python manage.py test blowcomotion.tests.test_member_auth_helpers -v 2
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add blowcomotion/member_auth.py blowcomotion/templates/emails/ blowcomotion/tests/test_member_auth_helpers.py
git commit -m "feat: add member_auth helpers (create_member_user, send_set_password_email, send_email_change_confirmation)"
```

---

### Task 4: Authentication Views

> **Parallel with Tasks 5, 6, 7, 8 — start after Task 3 completes.**

**Files:**
- Create: `blowcomotion/member_forms.py`
- Create: `blowcomotion/member_views.py` (auth views only — portal views added in Task 9)
- Create: `blowcomotion/member_urls.py`
- Modify: `blowcomotion/urls.py`
- Create: `blowcomotion/templates/member/login.html`
- Create: `blowcomotion/templates/member/set_password.html`
- Create: `blowcomotion/templates/member/get_access.html`
- Create: `blowcomotion/templates/member/password_reset.html`
- Create: `blowcomotion/templates/member/password_reset_done.html`
- Create: `blowcomotion/templates/member/password_reset_confirm.html`
- Create: `blowcomotion/templates/member/password_reset_complete.html`
- Test: `blowcomotion/tests/test_member_auth_views.py`

**Interfaces:**
- Consumes: `create_member_user(member)`, `send_set_password_email(member, request)` from `blowcomotion.member_auth`
- Consumes: `_validate_recaptcha(request)` from `blowcomotion.views`
- Produces: URL names `member-login`, `member-logout`, `member-set-password`, `member-get-access`, `password_reset_done`, `password_reset_confirm`, `password_reset_complete` (Django default names used by PasswordResetView internally)

- [ ] **Step 1: Write failing tests**

Create `blowcomotion/tests/test_member_auth_views.py`:

```python
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from blowcomotion.member_auth import create_member_user
from blowcomotion.models import Member, PasswordSetToken

User = get_user_model()


def make_member(**kwargs):
    defaults = dict(first_name="Sam", last_name="Player", email="sam@example.com")
    defaults.update(kwargs)
    return Member.objects.create(**defaults)


# Patch reCAPTCHA to always pass in tests
recaptcha_pass = patch(
    "blowcomotion.member_views._validate_recaptcha", return_value=(True, None)
)


class LoginViewTests(TestCase):
    def setUp(self):
        self.member = make_member()
        self.user = create_member_user(self.member)
        self.user.set_password("Str0ngP@ss!")
        self.user.save()

    def test_login_page_renders(self):
        response = self.client.get(reverse("member-login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form")

    @recaptcha_pass
    def test_valid_login_redirects_to_profile(self):
        response = self.client.post(
            reverse("member-login"),
            {"username": "sam@example.com", "password": "Str0ngP@ss!"},
        )
        self.assertRedirects(response, "/member/profile/", fetch_redirect_response=False)

    def test_honeypot_filled_redirects_silently(self):
        response = self.client.post(
            reverse("member-login"),
            {"username": "sam@example.com", "password": "x", "best_color": "red"},
        )
        self.assertEqual(response.status_code, 302)

    def test_recaptcha_fail_stays_on_login(self):
        with patch(
            "blowcomotion.member_views._validate_recaptcha",
            return_value=(False, "reCAPTCHA failed"),
        ):
            response = self.client.post(
                reverse("member-login"),
                {"username": "sam@example.com", "password": "Str0ngP@ss!"},
            )
        self.assertEqual(response.status_code, 200)


class SetPasswordViewTests(TestCase):
    def setUp(self):
        self.member = make_member()
        self.user = create_member_user(self.member)

    def _make_token(self):
        return PasswordSetToken.objects.create(member=self.member)

    def test_valid_token_renders_form(self):
        token = self._make_token()
        response = self.client.get(
            reverse("member-set-password", kwargs={"token_uuid": token.uuid})
        )
        self.assertEqual(response.status_code, 200)

    def test_used_token_returns_404(self):
        token = self._make_token()
        token.used = True
        token.save()
        response = self.client.get(
            reverse("member-set-password", kwargs={"token_uuid": token.uuid})
        )
        self.assertEqual(response.status_code, 404)

    def test_superseded_token_returns_404(self):
        token = self._make_token()
        token.superseded = True
        token.save()
        response = self.client.get(
            reverse("member-set-password", kwargs={"token_uuid": token.uuid})
        )
        self.assertEqual(response.status_code, 404)

    def test_expired_token_shows_expired_message(self):
        from datetime import timedelta
        from django.utils import timezone
        token = self._make_token()
        PasswordSetToken.objects.filter(pk=token.pk).update(
            created_at=timezone.now() - timedelta(hours=25)
        )
        response = self.client.get(
            reverse("member-set-password", kwargs={"token_uuid": token.uuid})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "expired")

    @recaptcha_pass
    def test_valid_submission_logs_in_user(self):
        token = self._make_token()
        response = self.client.post(
            reverse("member-set-password", kwargs={"token_uuid": token.uuid}),
            {"new_password1": "NewStr0ng@Pass!", "new_password2": "NewStr0ng@Pass!"},
        )
        self.assertRedirects(response, "/member/profile/", fetch_redirect_response=False)
        token.refresh_from_db()
        self.assertTrue(token.used)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   FROM_EMAIL="noreply@blowcomotion.org")
class GetAccessViewTests(TestCase):
    def test_get_renders_form(self):
        response = self.client.get(reverse("member-get-access"))
        self.assertEqual(response.status_code, 200)

    @recaptcha_pass
    def test_unknown_email_shows_generic_response(self):
        response = self.client.post(
            reverse("member-get-access"), {"email": "nobody@example.com"}
        )
        self.assertEqual(response.status_code, 200)
        from django.core import mail
        self.assertEqual(len(mail.outbox), 0)

    @recaptcha_pass
    def test_member_without_user_creates_account_and_sends_email(self):
        make_member(email="newbie@example.com")
        response = self.client.post(
            reverse("member-get-access"), {"email": "newbie@example.com"}
        )
        self.assertEqual(response.status_code, 200)
        from django.core import mail
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/member/set-password/", mail.outbox[0].body)

    @recaptcha_pass
    def test_member_with_user_sends_reset_email(self):
        from django.core import mail
        member = make_member(email="existing@example.com")
        user = create_member_user(member)
        user.set_password("SomePass123!")
        user.save()
        response = self.client.post(
            reverse("member-get-access"), {"email": "existing@example.com"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
```

- [ ] **Step 2: Run tests to see them fail**

```bash
python manage.py test blowcomotion.tests.test_member_auth_views -v 2
```

Expected: `ImportError` or URL `NoReverseMatch` for `member-login`.

- [ ] **Step 3: Create blowcomotion/member_forms.py**

```python
from django import forms


class GetAccessForm(forms.Form):
    email = forms.EmailField(
        label="Your member email address",
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "you@example.com"}),
    )
```

- [ ] **Step 4: Create blowcomotion/member_views.py (auth views)**

```python
import logging
from datetime import timedelta

from django_ratelimit.decorators import ratelimit

from django.contrib.auth import login, views as auth_views
from django.contrib.auth.forms import SetPasswordForm
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator

from blowcomotion.member_auth import create_member_user, send_set_password_email
from blowcomotion.member_forms import GetAccessForm
from blowcomotion.models import Member, PasswordSetToken
from blowcomotion.views import _validate_recaptcha

logger = logging.getLogger(__name__)

TOKEN_EXPIRY_HOURS = 24


# ── Login ──────────────────────────────────────────────────────────────────────

class MemberLoginView(auth_views.LoginView):
    template_name = "member/login.html"

    def post(self, request, *args, **kwargs):
        if request.POST.get("best_color"):
            return redirect("/")
        is_valid, error = _validate_recaptcha(request)
        if not is_valid:
            form = self.get_form_class()()
            return render(request, self.template_name, {
                "form": form,
                "recaptcha_error": error,
                "include_form_js": True,
            })
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["include_form_js"] = True
        return ctx


# ── Set Password ───────────────────────────────────────────────────────────────

@ratelimit(key="ip", rate="10/h", method="POST", block=True)
def set_password_view(request, token_uuid):
    token = get_object_or_404(
        PasswordSetToken, uuid=token_uuid, used=False, superseded=False
    )
    expiry = token.created_at + timedelta(hours=TOKEN_EXPIRY_HOURS)
    if timezone.now() > expiry:
        return render(request, "member/set_password.html", {"expired": True})

    if request.method == "POST":
        is_valid, error = _validate_recaptcha(request)
        if not is_valid:
            form = SetPasswordForm(user=token.member.user)
            return render(request, "member/set_password.html", {
                "form": form, "token": token,
                "recaptcha_error": error, "include_form_js": True,
            })
        form = SetPasswordForm(user=token.member.user, data=request.POST)
        if form.is_valid():
            form.save()
            token.used = True
            token.save(update_fields=["used"])
            login(request, token.member.user)
            logger.info(f"Member {token.member.pk} set password and logged in")
            return redirect("/member/profile/")
        return render(request, "member/set_password.html", {
            "form": form, "token": token, "include_form_js": True,
        })

    form = SetPasswordForm(user=token.member.user)
    return render(request, "member/set_password.html", {
        "form": form, "token": token, "include_form_js": True,
    })


# ── Password Reset ─────────────────────────────────────────────────────────────

class MemberPasswordResetView(auth_views.PasswordResetView):
    template_name = "member/password_reset.html"
    email_template_name = "registration/password_reset_email.html"  # Django default

    def post(self, request, *args, **kwargs):
        if request.POST.get("best_color"):
            return redirect("/")
        is_valid, error = _validate_recaptcha(request)
        if not is_valid:
            form = self.get_form_class()()
            return render(request, self.template_name, {
                "form": form, "recaptcha_error": error, "include_form_js": True,
            })
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        email = form.cleaned_data["email"]
        try:
            member = Member.objects.get(email__iexact=email, is_active=True)
        except Member.DoesNotExist:
            # No active member — generic response, no email sent
            logger.debug(f"Password reset attempted for non-member email: {email}")
            return redirect("password_reset_done")

        if not member.user_id or not member.user.has_usable_password():
            # Member has no account or unusable password → send set-password email
            if not member.user_id:
                create_member_user(member)
            send_set_password_email(member, self.request)
            logger.info(f"Sent set-password email (via reset flow) for member {member.pk}")
            return redirect("password_reset_done")

        # Member has a usable-password User → use Django's built-in reset
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["include_form_js"] = True
        return ctx


# ── Get Access ─────────────────────────────────────────────────────────────────

@ratelimit(key="ip", rate="10/h", method="POST", block=True)
def get_access_view(request):
    if request.method == "POST":
        if request.POST.get("best_color"):
            return redirect("/")
        is_valid, error = _validate_recaptcha(request)
        if not is_valid:
            form = GetAccessForm(request.POST)
            return render(request, "member/get_access.html", {
                "form": form, "recaptcha_error": error, "include_form_js": True,
            })
        form = GetAccessForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            try:
                member = Member.objects.get(email__iexact=email, is_active=True)
                if not member.user_id or not member.user.has_usable_password():
                    if not member.user_id:
                        create_member_user(member)
                    send_set_password_email(member, request)
                    logger.info(f"Get-access: sent set-password email to member {member.pk}")
                else:
                    # Member has account → send password reset email
                    from django.contrib.auth.forms import PasswordResetForm
                    reset_form = PasswordResetForm({"email": email})
                    if reset_form.is_valid():
                        reset_form.save(request=request, use_https=request.is_secure())
                    logger.info(f"Get-access: sent reset email to member {member.pk}")
            except Member.DoesNotExist:
                pass  # Generic response — no enumeration
            return render(request, "member/get_access.html", {
                "form": form, "sent": True,
            })
        return render(request, "member/get_access.html", {
            "form": form, "include_form_js": True,
        })

    form = GetAccessForm()
    return render(request, "member/get_access.html", {
        "form": form, "include_form_js": True,
    })
```

- [ ] **Step 5: Create blowcomotion/member_urls.py**

```python
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
    path("requests/", member_views.requests_view, name="member-requests"),
    path("", member_views.member_home, name="member-home"),
]
```

**Note:** `confirm_email_view`, `profile_view`, `requests_view`, and `member_home` are stubs added to `member_views.py` now so the URL file imports cleanly:

Append to `blowcomotion/member_views.py`:

```python
from django.contrib.auth.decorators import login_required


@login_required
def member_home(request):
    return redirect("member-profile")


@login_required
def profile_view(request):
    return render(request, "member/profile.html", {})


@login_required
def requests_view(request):
    return render(request, "member/requests.html", {})


def confirm_email_view(request, token_uuid):
    return render(request, "member/confirm_email_result.html", {})
```

These stubs are replaced with full implementations in Task 9.

- [ ] **Step 6: Register member_urls in blowcomotion/urls.py**

Add this import at the top of `blowcomotion/urls.py` (with the other imports):

```python
from blowcomotion import member_urls
```

Then add this line to `urlpatterns` BEFORE the static file patterns and BEFORE `wagtail_urls` (insert after the chart library paths but before the `if settings.DEBUG` block):

```python
    path("member/", include(member_urls)),
```

The `include` function needs to be imported — ensure `from django.urls import include, path` is at the top.

- [ ] **Step 7: Create auth templates**

Create `blowcomotion/templates/member/login.html`:

```html
{% extends "base.html" %}
{% block title %}Member Login — Blowcomotion{% endblock %}

{% block content %}
<div class="container py-5">
    <div class="row justify-content-center">
        <div class="col-md-6 col-lg-5">
            <h1 class="mb-4 text-center">Member Login</h1>
            {% if recaptcha_error %}<div class="alert alert-danger">{{ recaptcha_error }}</div>{% endif %}
            <form method="post" id="member-form">
                {% csrf_token %}
                <input type="text" name="best_color" class="best-color" style="display:none;" tabindex="-1" autocomplete="off">
                <input type="hidden" name="g-recaptcha-response" value="">
                <div class="mb-3">
                    <label for="id_username" class="form-label">Email address</label>
                    <input type="email" name="username" id="id_username" class="form-control" required autofocus>
                    {% if form.username.errors %}<div class="text-danger small">{{ form.username.errors }}</div>{% endif %}
                </div>
                <div class="mb-3">
                    <label for="id_password" class="form-label">Password</label>
                    <input type="password" name="password" id="id_password" class="form-control" required>
                    {% if form.password.errors %}<div class="text-danger small">{{ form.password.errors }}</div>{% endif %}
                </div>
                {% if form.non_field_errors %}<div class="alert alert-danger">{{ form.non_field_errors }}</div>{% endif %}
                <button type="submit" class="site-btn w-100">Log In</button>
            </form>
            <div class="mt-3 text-center small">
                <a href="{% url 'member-get-access' %}">New member? Get access →</a>
                &nbsp;|&nbsp;
                <a href="{% url 'member-password-reset' %}">Forgot password?</a>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
{{ block.super }}
{% if include_form_js %}
<script>
(function() {
    var form = document.getElementById('member-form');
    if (!form || typeof grecaptcha === 'undefined' || !window.RECAPTCHA_SITE_KEY) return;
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        var self = this;
        grecaptcha.ready(function() {
            grecaptcha.execute(window.RECAPTCHA_SITE_KEY, {action: 'submit'}).then(function(token) {
                self.querySelector('input[name="g-recaptcha-response"]').value = token;
                self.submit();
            }).catch(function() { self.submit(); });
        });
    });
})();
</script>
{% endif %}
{% endblock %}
```

Create `blowcomotion/templates/member/set_password.html`:

```html
{% extends "base.html" %}
{% block title %}Set Your Password — Blowcomotion{% endblock %}

{% block content %}
<div class="container py-5">
    <div class="row justify-content-center">
        <div class="col-md-6 col-lg-5">
            {% if expired %}
                <h1 class="mb-3">Link Expired</h1>
                <p>This set-password link has expired. <a href="{% url 'member-get-access' %}">Request a new one</a>.</p>
            {% else %}
                <h1 class="mb-4 text-center">Set Your Password</h1>
                {% if recaptcha_error %}<div class="alert alert-danger">{{ recaptcha_error }}</div>{% endif %}
                <form method="post" id="member-form">
                    {% csrf_token %}
                    <input type="hidden" name="g-recaptcha-response" value="">
                    {% for field in form %}
                    <div class="mb-3">
                        <label for="{{ field.id_for_label }}" class="form-label">{{ field.label }}</label>
                        {{ field }}
                        {% if field.errors %}<div class="text-danger small">{{ field.errors }}</div>{% endif %}
                    </div>
                    {% endfor %}
                    {% if form.non_field_errors %}<div class="alert alert-danger">{{ form.non_field_errors }}</div>{% endif %}
                    <button type="submit" class="site-btn w-100">Set Password</button>
                </form>
            {% endif %}
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
{{ block.super }}
{% if include_form_js %}
<script>
(function() {
    var form = document.getElementById('member-form');
    if (!form || typeof grecaptcha === 'undefined' || !window.RECAPTCHA_SITE_KEY) return;
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        var self = this;
        grecaptcha.ready(function() {
            grecaptcha.execute(window.RECAPTCHA_SITE_KEY, {action: 'submit'}).then(function(token) {
                self.querySelector('input[name="g-recaptcha-response"]').value = token;
                self.submit();
            }).catch(function() { self.submit(); });
        });
    });
})();
</script>
{% endif %}
{% endblock %}
```

Create `blowcomotion/templates/member/get_access.html`:

```html
{% extends "base.html" %}
{% block title %}Get Member Access — Blowcomotion{% endblock %}

{% block content %}
<div class="container py-5">
    <div class="row justify-content-center">
        <div class="col-md-6 col-lg-5">
            <h1 class="mb-4 text-center">Get Member Access</h1>
            {% if sent %}
                <div class="alert alert-success">If you're a member, check your email for next steps.</div>
            {% else %}
                {% if recaptcha_error %}<div class="alert alert-danger">{{ recaptcha_error }}</div>{% endif %}
                <p class="text-muted mb-4">Enter your member email address and we'll send you a link to set up your account.</p>
                <form method="post" id="member-form">
                    {% csrf_token %}
                    <input type="text" name="best_color" class="best-color" style="display:none;" tabindex="-1" autocomplete="off">
                    <input type="hidden" name="g-recaptcha-response" value="">
                    <div class="mb-3">
                        <label for="{{ form.email.id_for_label }}" class="form-label">{{ form.email.label }}</label>
                        {{ form.email }}
                        {% if form.email.errors %}<div class="text-danger small">{{ form.email.errors }}</div>{% endif %}
                    </div>
                    <button type="submit" class="site-btn w-100">Send Access Link</button>
                </form>
                <div class="mt-3 text-center small">
                    Already have a password? <a href="{% url 'member-login' %}">Log in</a>
                </div>
            {% endif %}
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
{{ block.super }}
{% if include_form_js %}
<script>
(function() {
    var form = document.getElementById('member-form');
    if (!form || typeof grecaptcha === 'undefined' || !window.RECAPTCHA_SITE_KEY) return;
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        var self = this;
        grecaptcha.ready(function() {
            grecaptcha.execute(window.RECAPTCHA_SITE_KEY, {action: 'submit'}).then(function(token) {
                self.querySelector('input[name="g-recaptcha-response"]').value = token;
                self.submit();
            }).catch(function() { self.submit(); });
        });
    });
})();
</script>
{% endif %}
{% endblock %}
```

Create `blowcomotion/templates/member/password_reset.html`:

```html
{% extends "base.html" %}
{% block title %}Reset Password — Blowcomotion{% endblock %}

{% block content %}
<div class="container py-5">
    <div class="row justify-content-center">
        <div class="col-md-6 col-lg-5">
            <h1 class="mb-4 text-center">Reset Your Password</h1>
            {% if recaptcha_error %}<div class="alert alert-danger">{{ recaptcha_error }}</div>{% endif %}
            <form method="post" id="member-form">
                {% csrf_token %}
                <input type="text" name="best_color" class="best-color" style="display:none;" tabindex="-1" autocomplete="off">
                <input type="hidden" name="g-recaptcha-response" value="">
                <div class="mb-3">
                    <label for="id_email" class="form-label">Email address</label>
                    <input type="email" name="email" id="id_email" class="form-control" required>
                </div>
                <button type="submit" class="site-btn w-100">Send Reset Link</button>
            </form>
            <div class="mt-3 text-center small">
                <a href="{% url 'member-login' %}">Back to login</a>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
{{ block.super }}
{% if include_form_js %}
<script>
(function() {
    var form = document.getElementById('member-form');
    if (!form || typeof grecaptcha === 'undefined' || !window.RECAPTCHA_SITE_KEY) return;
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        var self = this;
        grecaptcha.ready(function() {
            grecaptcha.execute(window.RECAPTCHA_SITE_KEY, {action: 'submit'}).then(function(token) {
                self.querySelector('input[name="g-recaptcha-response"]').value = token;
                self.submit();
            }).catch(function() { self.submit(); });
        });
    });
})();
</script>
{% endif %}
{% endblock %}
```

Create `blowcomotion/templates/member/password_reset_done.html`:

```html
{% extends "base.html" %}
{% block title %}Check Your Email — Blowcomotion{% endblock %}
{% block content %}
<div class="container py-5 text-center">
    <h1 class="mb-3">Check Your Email</h1>
    <p class="lead">If you're a member, you'll receive an email with next steps shortly.</p>
    <a href="{% url 'member-login' %}" class="site-btn mt-3">Back to Login</a>
</div>
{% endblock %}
```

Create `blowcomotion/templates/member/password_reset_confirm.html`:

```html
{% extends "base.html" %}
{% block title %}Choose New Password — Blowcomotion{% endblock %}
{% block content %}
<div class="container py-5">
    <div class="row justify-content-center">
        <div class="col-md-6 col-lg-5">
            {% if validlink %}
                <h1 class="mb-4 text-center">Choose a New Password</h1>
                <form method="post" id="member-form">
                    {% csrf_token %}
                    <input type="hidden" name="g-recaptcha-response" value="">
                    {% for field in form %}
                    <div class="mb-3">
                        <label for="{{ field.id_for_label }}" class="form-label">{{ field.label }}</label>
                        {{ field }}
                        {% if field.errors %}<div class="text-danger small">{{ field.errors }}</div>{% endif %}
                    </div>
                    {% endfor %}
                    <button type="submit" class="site-btn w-100">Set New Password</button>
                </form>
            {% else %}
                <h1>Link Invalid</h1>
                <p>This reset link is invalid or has already been used. <a href="{% url 'member-password-reset' %}">Request a new one</a>.</p>
            {% endif %}
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
{{ block.super }}
<script>
(function() {
    var form = document.getElementById('member-form');
    if (!form || typeof grecaptcha === 'undefined' || !window.RECAPTCHA_SITE_KEY) return;
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        var self = this;
        grecaptcha.ready(function() {
            grecaptcha.execute(window.RECAPTCHA_SITE_KEY, {action: 'submit'}).then(function(token) {
                self.querySelector('input[name="g-recaptcha-response"]').value = token;
                self.submit();
            }).catch(function() { self.submit(); });
        });
    });
})();
</script>
{% endblock %}
```

Create `blowcomotion/templates/member/password_reset_complete.html`:

```html
{% extends "base.html" %}
{% block title %}Password Changed — Blowcomotion{% endblock %}
{% block content %}
<div class="container py-5 text-center">
    <h1 class="mb-3">Password Changed</h1>
    <p class="lead">Your password has been set. You can now log in.</p>
    <a href="{% url 'member-login' %}" class="site-btn mt-3">Log In</a>
</div>
{% endblock %}
```

Also create a stub `blowcomotion/templates/member/confirm_email_result.html` (full version in Task 9):

```html
{% extends "base.html" %}
{% block title %}Email Confirmation — Blowcomotion{% endblock %}
{% block content %}
<div class="container py-5 text-center">
    <p>Processing…</p>
</div>
{% endblock %}
```

- [ ] **Step 8: Run tests**

```bash
python manage.py test blowcomotion.tests.test_member_auth_views -v 2
```

Expected: All tests PASS.

- [ ] **Step 9: Commit**

```bash
git add blowcomotion/member_forms.py blowcomotion/member_views.py blowcomotion/member_urls.py blowcomotion/urls.py blowcomotion/templates/member/ blowcomotion/tests/test_member_auth_views.py
git commit -m "feat: add member auth views (login, set-password, get-access, password-reset)"
```

---

### Task 5: Auto-logout Middleware

> **Parallel with Tasks 4, 6, 7, 8 — start after Task 3 completes.**

**Files:**
- Create: `blowcomotion/middleware.py`
- Modify: `blowcomotion/settings/base.py` (add middleware to MIDDLEWARE list)
- Test: `blowcomotion/tests/test_member_middleware.py`

**Interfaces:**
- Consumes: `settings.MEMBER_IDLE_TIMEOUT` (int, seconds) — set in Task 1
- Produces: `MemberIdleLogoutMiddleware` — flushes session and redirects to LOGIN_URL when a non-staff authenticated user has been idle for `MEMBER_IDLE_TIMEOUT` seconds; updates `session["last_activity"]` on each request

- [ ] **Step 1: Write failing tests**

Create `blowcomotion/tests/test_member_middleware.py`:

```python
import time

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

User = get_user_model()


def _make_user(staff=False):
    username = f"user_{User.objects.count()}@example.com"
    u = User.objects.create_user(username=username, email=username, password="pass")
    u.is_staff = staff
    u.save()
    return u


def _make_request(user, session_data=None):
    factory = RequestFactory()
    request = factory.get("/member/profile/")
    request.user = user
    request.session = {}
    if session_data:
        request.session.update(session_data)
    return request


class MemberIdleLogoutMiddlewareTests(TestCase):
    def get_middleware(self):
        from blowcomotion.middleware import MemberIdleLogoutMiddleware
        return MemberIdleLogoutMiddleware(get_response=lambda r: None)

    @override_settings(MEMBER_IDLE_TIMEOUT=3600)
    def test_sets_last_activity_on_first_request(self):
        mw = self.get_middleware()
        user = _make_user()
        request = _make_request(user)
        mw.process_request(request)
        self.assertIn("last_activity", request.session)

    @override_settings(MEMBER_IDLE_TIMEOUT=3600)
    def test_active_session_allowed(self):
        from django.utils import timezone
        mw = self.get_middleware()
        user = _make_user()
        recent = timezone.now().timestamp() - 100
        request = _make_request(user, {"last_activity": recent})
        result = mw.process_request(request)
        self.assertIsNone(result)  # no redirect

    @override_settings(MEMBER_IDLE_TIMEOUT=60)
    def test_idle_session_redirects_to_login(self):
        from django.utils import timezone
        mw = self.get_middleware()
        user = _make_user()
        expired = timezone.now().timestamp() - 120
        request = _make_request(user, {"last_activity": expired})
        result = mw.process_request(request)
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 302)
        self.assertIn("/member/login/", result["Location"])

    @override_settings(MEMBER_IDLE_TIMEOUT=60)
    def test_staff_user_not_affected(self):
        from django.utils import timezone
        mw = self.get_middleware()
        staff_user = _make_user(staff=True)
        expired = timezone.now().timestamp() - 120
        request = _make_request(staff_user, {"last_activity": expired})
        result = mw.process_request(request)
        self.assertIsNone(result)  # staff not logged out

    @override_settings(MEMBER_IDLE_TIMEOUT=3600)
    def test_anonymous_user_not_affected(self):
        from django.contrib.auth.models import AnonymousUser
        mw = self.get_middleware()
        request = _make_request(AnonymousUser())
        result = mw.process_request(request)
        self.assertIsNone(result)
```

- [ ] **Step 2: Run tests to see them fail**

```bash
python manage.py test blowcomotion.tests.test_member_middleware -v 2
```

Expected: `ImportError: cannot import name 'MemberIdleLogoutMiddleware'`

- [ ] **Step 3: Create blowcomotion/middleware.py**

```python
import logging

from django.conf import settings
from django.shortcuts import redirect
from django.utils import timezone

logger = logging.getLogger(__name__)


class MemberIdleLogoutMiddleware:
    """Logs out non-staff members after MEMBER_IDLE_TIMEOUT seconds of inactivity."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        result = self.process_request(request)
        if result is not None:
            return result
        return self.get_response(request)

    def process_request(self, request):
        if not request.user.is_authenticated or request.user.is_staff:
            return None

        timeout = getattr(settings, "MEMBER_IDLE_TIMEOUT", 3600)
        now = timezone.now().timestamp()
        last_activity = request.session.get("last_activity")

        if last_activity is not None and (now - last_activity) > timeout:
            request.session.flush()
            login_url = getattr(settings, "LOGIN_URL", "/member/login/")
            logger.info(f"Member session expired for user {request.user.pk}")
            return redirect(f"{login_url}?next={request.path}")

        request.session["last_activity"] = now
        return None
```

- [ ] **Step 4: Register middleware in settings/base.py**

In `blowcomotion/settings/base.py`, add `"blowcomotion.middleware.MemberIdleLogoutMiddleware"` to MIDDLEWARE after `axes.middleware.AxesMiddleware`:

```python
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "axes.middleware.AxesMiddleware",
    "blowcomotion.middleware.MemberIdleLogoutMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
    "livereload.middleware.LiveReloadScript",
]
```

- [ ] **Step 5: Run tests**

```bash
python manage.py test blowcomotion.tests.test_member_middleware -v 2
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add blowcomotion/middleware.py blowcomotion/settings/base.py blowcomotion/tests/test_member_middleware.py
git commit -m "feat: add MemberIdleLogoutMiddleware (60-min idle timeout for non-staff members)"
```

---

### Task 6: invite_members Management Command

> **Parallel with Tasks 4, 5, 7, 8 — start after Task 3 completes.**

**Files:**
- Create: `blowcomotion/management/commands/invite_members.py`
- Test: `blowcomotion/tests/test_invite_members_command.py`

**Interfaces:**
- Consumes: `create_member_user(member)`, `send_set_password_email(member, request)` from `blowcomotion.member_auth`
- Produces: `invite_members` management command with `--dry-run` and `--member-id` flags

- [ ] **Step 1: Write failing tests**

Create `blowcomotion/tests/test_invite_members_command.py`:

```python
from io import StringIO
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from blowcomotion.member_auth import create_member_user
from blowcomotion.models import Member

User = get_user_model()


def make_member(email, active=True, **kwargs):
    return Member.objects.create(
        first_name="Test", last_name="Member", email=email, is_active=active, **kwargs
    )


# Patch send_set_password_email so no real emails are sent
patch_email = patch("blowcomotion.management.commands.invite_members.send_set_password_email")
patch_request = patch(
    "blowcomotion.management.commands.invite_members.HttpRequest",
    return_value=MagicMock(),
)


class InviteMembersCommandTests(TestCase):
    @patch_email
    @patch_request
    def test_invites_active_members_without_user(self, mock_request, mock_email):
        m = make_member("invite1@example.com")
        out = StringIO()
        call_command("invite_members", stdout=out)
        mock_email.assert_called_once()
        m.refresh_from_db()
        self.assertIsNotNone(m.user_id)

    @patch_email
    @patch_request
    def test_skips_members_with_existing_user(self, mock_request, mock_email):
        m = make_member("existing@example.com")
        create_member_user(m)
        out = StringIO()
        call_command("invite_members", stdout=out)
        mock_email.assert_not_called()

    @patch_email
    @patch_request
    def test_skips_inactive_members(self, mock_request, mock_email):
        make_member("inactive@example.com", active=False)
        call_command("invite_members", stdout=StringIO())
        mock_email.assert_not_called()

    @patch_email
    @patch_request
    def test_dry_run_sends_no_emails_creates_no_users(self, mock_request, mock_email):
        m = make_member("dryrun@example.com")
        out = StringIO()
        call_command("invite_members", "--dry-run", stdout=out)
        mock_email.assert_not_called()
        m.refresh_from_db()
        self.assertIsNone(m.user_id)
        self.assertIn("dryrun@example.com", out.getvalue())

    @patch_email
    @patch_request
    def test_member_id_flag_processes_single_member(self, mock_request, mock_email):
        m1 = make_member("single1@example.com")
        m2 = make_member("single2@example.com")
        call_command("invite_members", f"--member-id={m1.pk}", stdout=StringIO())
        mock_email.assert_called_once()
        m2.refresh_from_db()
        self.assertIsNone(m2.user_id)

    @patch_email
    @patch_request
    def test_error_on_one_member_does_not_abort_rest(self, mock_request, mock_email):
        m1 = make_member("fail@example.com")
        m2 = make_member("ok@example.com")

        call_count = [0]
        def email_side_effect(member, request):
            call_count[0] += 1
            if member.email == "fail@example.com":
                raise Exception("SMTP error")
        mock_email.side_effect = email_side_effect

        out = StringIO()
        call_command("invite_members", stdout=out)
        self.assertEqual(call_count[0], 2)

    @patch_email
    @patch_request
    def test_logs_summary(self, mock_request, mock_email):
        make_member("a@example.com")
        make_member("b@example.com")
        out = StringIO()
        call_command("invite_members", stdout=out)
        output = out.getvalue()
        self.assertIn("invited", output.lower())
```

- [ ] **Step 2: Run tests to see them fail**

```bash
python manage.py test blowcomotion.tests.test_invite_members_command -v 2
```

Expected: `CommandError` or `ModuleNotFoundError`.

- [ ] **Step 3: Create the management command**

Create `blowcomotion/management/commands/invite_members.py`:

```python
"""
Invite all active members without accounts to set their password.

Usage:
    python manage.py invite_members [--dry-run] [--member-id MEMBER_ID]
"""
import logging

from django.core.management.base import BaseCommand
from django.http import HttpRequest

from blowcomotion.member_auth import create_member_user, send_set_password_email
from blowcomotion.models import Member

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send set-password invitations to active members without accounts"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print who would be invited without sending emails or creating users",
        )
        parser.add_argument(
            "--member-id",
            type=int,
            default=None,
            help="Process a single member by ID (for testing)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        member_id = options["member_id"]

        qs = Member.objects.filter(is_active=True, user__isnull=True)
        if member_id:
            qs = qs.filter(pk=member_id)

        # Build a minimal request so build_absolute_uri works
        request = HttpRequest()
        request.META["SERVER_NAME"] = "www.blowcomotion.org"
        request.META["SERVER_PORT"] = "443"
        request.META["wsgi.url_scheme"] = "https"

        invited = skipped = errored = 0

        for member in qs:
            if not member.email:
                self.stdout.write(f"  SKIP (no email): {member}")
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(f"  DRY RUN — would invite: {member} <{member.email}>")
                invited += 1
                continue

            try:
                create_member_user(member)
                send_set_password_email(member, request)
                self.stdout.write(f"  Invited: {member} <{member.email}>")
                invited += 1
            except Exception as exc:
                self.stderr.write(f"  ERROR for {member} <{member.email}>: {exc}")
                logger.error(f"invite_members: error inviting member {member.pk}: {exc}")
                errored += 1

        prefix = "Would invite" if dry_run else "Invited"
        self.stdout.write(
            f"\nDone. {prefix}: {invited} | Skipped: {skipped} | Errored: {errored}"
        )
```

- [ ] **Step 4: Run tests**

```bash
python manage.py test blowcomotion.tests.test_invite_members_command -v 2
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add blowcomotion/management/commands/invite_members.py blowcomotion/tests/test_invite_members_command.py
git commit -m "feat: add invite_members management command with --dry-run and --member-id flags"
```

---

### Task 7: Member Signup Integration

> **Parallel with Tasks 4, 5, 6, 8 — start after Task 3 completes.**

**Files:**
- Modify: `blowcomotion/views.py` (update `_process_member_signup`)
- Test: `blowcomotion/tests/test_member_signup_go3.py` (extend existing)

**Interfaces:**
- Consumes: `create_member_user(member)`, `send_set_password_email(member, request)` from `blowcomotion.member_auth`

- [ ] **Step 1: Write failing test**

Open `blowcomotion/tests/test_member_signup_go3.py` and append:

```python
class MemberSignupCreatesUserTests(TestCase):
    """After signup, a User is created and a set-password email is sent."""

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        FROM_EMAIL="noreply@blowcomotion.org",
        RECAPTCHA_PUBLIC_KEY=None,
        RECAPTCHA_PRIVATE_KEY=None,
        GIGO_API_URL=None,
    )
    @patch("blowcomotion.views.send_member_to_go3_band_invite")
    def test_signup_creates_user_and_sends_set_password_email(self, mock_go3):
        mock_go3.return_value = {"status": "success", "message": "ok"}
        from django.core import mail
        from django.contrib.auth import get_user_model

        User = get_user_model()

        response = self.client.post(
            "/process-form/",
            {
                "form_type": "member_signup",
                "first_name": "Alex",
                "last_name": "Musician",
                "email": "alex@example.com",
            },
        )
        # Set-password email should have been sent
        self.assertTrue(
            any("/member/set-password/" in m.body for m in mail.outbox),
            "Expected a set-password email but none found",
        )
        # A User linked to the new Member should exist
        from blowcomotion.models import Member
        member = Member.objects.get(email="alex@example.com")
        self.assertIsNotNone(member.user_id)
        user = User.objects.get(pk=member.user_id)
        self.assertFalse(user.has_usable_password())
```

- [ ] **Step 2: Run test to see it fail**

```bash
python manage.py test blowcomotion.tests.test_member_signup_go3.MemberSignupCreatesUserTests -v 2
```

Expected: `AssertionError` — no set-password email in outbox.

- [ ] **Step 3: Update _process_member_signup in views.py**

In `blowcomotion/views.py`, add this import near the top (with the other blowcomotion imports):

```python
from blowcomotion.member_auth import create_member_user, send_set_password_email
```

Find `_process_member_signup` — it ends with an admin notification email send and a `return` dict. After the GO3 invite block (around line 769) but before the final `return`, add:

```python
        # Create a User account and send set-password email if the member has an email
        if member.email:
            try:
                create_member_user(member)
                send_set_password_email(member, request)
                logger.info(f"Sent set-password email to new member {member.pk}")
            except Exception as e:
                logger.warning(f"Could not send set-password email to new member {member.pk}: {e}")
```

- [ ] **Step 4: Run test**

```bash
python manage.py test blowcomotion.tests.test_member_signup_go3.MemberSignupCreatesUserTests -v 2
```

Expected: PASS.

- [ ] **Step 5: Run full test suite to confirm no regressions**

```bash
python manage.py test blowcomotion.tests.test_member_signup_go3 -v 2
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add blowcomotion/views.py blowcomotion/tests/test_member_signup_go3.py
git commit -m "feat: create user account and send set-password email on new member signup"
```

---

### Task 8: Member.save() Email Drift Guard

> **Parallel with Tasks 4, 5, 6, 7 — start after Task 2 completes (does not need Task 3).**

This task verifies the drift guard added in Task 2 is working and adds an integration test in the right file.

**Files:**
- Test: `blowcomotion/tests/test_member_auth_helpers.py` (tests already written in Task 2 Step 1 — verify they all pass)

**Interfaces:**
- Consumes: `Member.save()` from `blowcomotion.models` (modified in Task 2)

- [ ] **Step 1: Run the drift guard tests**

```bash
python manage.py test blowcomotion.tests.test_member_auth_helpers.MemberSaveEmailDriftTests -v 2
```

Expected: All tests PASS (these were written in Task 2 and should already be green).

- [ ] **Step 2: Run full model test suite**

```bash
python manage.py test blowcomotion.tests.test_member_model -v 2
```

Expected: All existing tests PASS (no regressions from model changes).

- [ ] **Step 3: Commit (if any fixes were needed)**

If Task 2's drift guard code needed adjustment:

```bash
git add blowcomotion/models.py
git commit -m "fix: correct Member.save() email drift guard edge case"
```

---

### Task 9: Member Portal Views

> **Parallel with Task 10 — start after Task 4 completes.**

**Files:**
- Modify: `blowcomotion/member_views.py` (replace stubs with full profile, requests, confirm-email views)
- Modify: `blowcomotion/member_forms.py` (add MemberProfileForm)
- Create: `blowcomotion/templates/member/portal_base.html`
- Create: `blowcomotion/templates/member/profile.html`
- Create: `blowcomotion/templates/member/requests.html`
- Replace: `blowcomotion/templates/member/confirm_email_result.html` (full version)
- Test: `blowcomotion/tests/test_member_portal.py`

**Interfaces:**
- Consumes: `send_email_change_confirmation(member, new_email, request)` from `blowcomotion.member_auth`
- Consumes: URL names `member-login`, `member-profile`, `member-requests` from `blowcomotion.member_urls`
- Produces: `member-profile` view (saves all non-admin Member fields; triggers email-change confirmation flow), `member-requests` view (stub), `confirm_email_view` (confirms email change)

- [ ] **Step 1: Write failing tests**

Create `blowcomotion/tests/test_member_portal.py`:

```python
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from blowcomotion.member_auth import create_member_user
from blowcomotion.models import EmailChangeToken, Member

User = get_user_model()


def make_member(**kwargs):
    defaults = dict(first_name="Robin", last_name="Player", email="robin@example.com")
    defaults.update(kwargs)
    return Member.objects.create(**defaults)


class PortalAuthGateTests(TestCase):
    def test_profile_redirects_anonymous_to_login(self):
        response = self.client.get(reverse("member-profile"))
        self.assertRedirects(
            response,
            "/member/login/?next=/member/profile/",
            fetch_redirect_response=False,
        )

    def test_requests_redirects_anonymous_to_login(self):
        response = self.client.get(reverse("member-requests"))
        self.assertRedirects(
            response,
            "/member/login/?next=/member/requests/",
            fetch_redirect_response=False,
        )


class ProfileViewTests(TestCase):
    def setUp(self):
        self.member = make_member()
        self.user = create_member_user(self.member)
        self.user.set_password("Pass123!")
        self.user.save()
        self.client.login(username="robin@example.com", password="Pass123!")

    def test_profile_page_renders(self):
        response = self.client.get(reverse("member-profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Robin")

    def test_profile_saves_name_change(self):
        response = self.client.post(
            reverse("member-profile"),
            {
                "first_name": "Robin",
                "last_name": "Player",
                "preferred_name": "Robbie",
                "email": "robin@example.com",
                "notify_rental_updates": True,
                "notify_reminders": True,
                "notify_announcements": True,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.preferred_name, "Robbie")

    def test_email_change_sets_pending_email(self):
        from django.test import override_settings
        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            FROM_EMAIL="noreply@blowcomotion.org",
        ):
            self.client.post(
                reverse("member-profile"),
                {
                    "first_name": "Robin",
                    "last_name": "Player",
                    "email": "newemail@example.com",
                    "notify_rental_updates": True,
                    "notify_reminders": True,
                    "notify_announcements": True,
                },
            )
        self.member.refresh_from_db()
        self.assertEqual(self.member.pending_email, "newemail@example.com")
        self.assertEqual(self.member.email, "robin@example.com")  # unchanged until confirmed

    def test_email_unchanged_does_not_send_confirmation(self):
        from django.core import mail
        with self.settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            FROM_EMAIL="noreply@blowcomotion.org",
        ):
            self.client.post(
                reverse("member-profile"),
                {
                    "first_name": "Robin",
                    "last_name": "Player",
                    "email": "robin@example.com",  # same email
                    "notify_rental_updates": True,
                    "notify_reminders": True,
                    "notify_announcements": True,
                },
            )
        self.assertEqual(len(mail.outbox), 0)


class ConfirmEmailViewTests(TestCase):
    def setUp(self):
        self.member = make_member()
        self.user = create_member_user(self.member)
        self.user.set_password("Pass123!")
        self.user.save()

    def test_valid_token_updates_email(self):
        from datetime import timedelta
        from django.utils import timezone
        token = EmailChangeToken.objects.create(
            member=self.member, new_email="confirmed@example.com"
        )
        response = self.client.get(
            reverse("member-confirm-email", kwargs={"token_uuid": token.uuid})
        )
        self.assertEqual(response.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.email, "confirmed@example.com")
        self.assertIsNone(self.member.pending_email)
        token.refresh_from_db()
        self.assertTrue(token.used)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "confirmed@example.com")
        self.assertEqual(self.user.username, "confirmed@example.com")

    def test_used_token_shows_error(self):
        token = EmailChangeToken.objects.create(
            member=self.member, new_email="x@example.com", used=True
        )
        response = self.client.get(
            reverse("member-confirm-email", kwargs={"token_uuid": token.uuid})
        )
        self.assertContains(response, "invalid")

    def test_expired_token_shows_error(self):
        from datetime import timedelta
        from django.utils import timezone
        token = EmailChangeToken.objects.create(
            member=self.member, new_email="x@example.com"
        )
        EmailChangeToken.objects.filter(pk=token.pk).update(
            created_at=timezone.now() - timedelta(hours=25)
        )
        response = self.client.get(
            reverse("member-confirm-email", kwargs={"token_uuid": token.uuid})
        )
        self.assertContains(response, "expired")


class RequestsStubTests(TestCase):
    def setUp(self):
        member = make_member()
        user = create_member_user(member)
        user.set_password("Pass123!")
        user.save()
        self.client.login(username="robin@example.com", password="Pass123!")

    def test_requests_page_renders(self):
        response = self.client.get(reverse("member-requests"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Coming soon")
```

- [ ] **Step 2: Run tests to see them fail**

```bash
python manage.py test blowcomotion.tests.test_member_portal -v 2
```

Expected: Most tests fail because profile_view is a stub.

- [ ] **Step 3: Add MemberProfileForm to member_forms.py**

Append to `blowcomotion/member_forms.py`:

```python
from blowcomotion.models import Instrument, Member


class MemberProfileForm(forms.ModelForm):
    additional_instruments = forms.ModelMultipleChoiceField(
        queryset=Instrument.objects.all().order_by("name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Additional instruments",
    )

    class Meta:
        model = Member
        fields = [
            "first_name",
            "last_name",
            "preferred_name",
            "email",
            "phone",
            "address",
            "city",
            "state",
            "zip_code",
            "country",
            "birth_month",
            "birth_day",
            "birth_year",
            "emergency_contact",
            "bio",
            "inspired_by",
            "primary_instrument",
            "image",
            "notify_rental_updates",
            "notify_reminders",
            "notify_announcements",
        ]
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 4}),
            "emergency_contact": forms.Textarea(attrs={"rows": 2}),
            "inspired_by": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["additional_instruments"].initial = list(
                self.instance.additional_instruments.values_list("instrument_id", flat=True)
            )
        for field in self.fields.values():
            if hasattr(field.widget, "attrs"):
                field.widget.attrs.setdefault("class", "form-control")
```

- [ ] **Step 4: Replace stub views in member_views.py**

Replace the stub `profile_view`, `requests_view`, `confirm_email_view`, and `member_home` in `blowcomotion/member_views.py` with:

```python
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from blowcomotion.member_auth import send_email_change_confirmation
from blowcomotion.models import EmailChangeToken, MemberInstrument

User = get_user_model()


@login_required
def member_home(request):
    return redirect("member-profile")


@login_required
def profile_view(request):
    from blowcomotion.member_forms import MemberProfileForm
    member = request.user.member

    if request.method == "POST":
        form = MemberProfileForm(request.POST, request.FILES, instance=member)
        if form.is_valid():
            instance = form.save(commit=False)
            new_email = form.cleaned_data.get("email") or ""
            email_changed = new_email and new_email != member.email

            if email_changed:
                instance.email = member.email  # hold until confirmed
            instance.save(sync_go3=False)

            # Rebuild additional instruments
            member.additional_instruments.all().delete()
            for instrument in form.cleaned_data.get("additional_instruments", []):
                MemberInstrument.objects.create(member=member, instrument=instrument)

            if email_changed:
                send_email_change_confirmation(member, new_email, request)
                messages.success(
                    request,
                    f"Profile saved. A confirmation email has been sent to {new_email}.",
                )
            else:
                messages.success(request, "Profile saved.")
            return redirect("member-profile")
        return render(request, "member/profile.html", {
            "form": form, "member": member, "include_form_js": True,
        })

    form = MemberProfileForm(instance=member)
    return render(request, "member/profile.html", {
        "form": form, "member": member, "include_form_js": True,
    })


@login_required
def requests_view(request):
    return render(request, "member/requests.html", {"member": request.user.member})


def confirm_email_view(request, token_uuid):
    from blowcomotion.models import EmailChangeToken
    try:
        token = EmailChangeToken.objects.get(uuid=token_uuid)
    except EmailChangeToken.DoesNotExist:
        return render(request, "member/confirm_email_result.html", {"invalid": True})

    if token.used:
        return render(request, "member/confirm_email_result.html", {"invalid": True})

    expiry = token.created_at + timedelta(hours=24)
    if timezone.now() > expiry:
        return render(request, "member/confirm_email_result.html", {"expired": True})

    member = token.member
    new_email = token.new_email

    member.email = new_email
    member.pending_email = None
    member.save(update_fields=["email", "pending_email"], sync_go3=False)

    token.used = True
    token.save(update_fields=["used"])

    if member.user_id:
        try:
            user = User.objects.get(pk=member.user_id)
            user.email = new_email
            user.username = new_email
            user.save(update_fields=["email", "username"])
        except User.DoesNotExist:
            pass

    logger.info(f"Email confirmed for member {member.pk}: {new_email}")
    return render(request, "member/confirm_email_result.html", {"confirmed": True, "new_email": new_email})
```

Also add `from django.contrib import messages` to the imports at the top of `member_views.py`.

- [ ] **Step 5: Create portal templates**

Create `blowcomotion/templates/member/portal_base.html`:

```html
{% extends "base.html" %}
{% block content %}
<div class="container py-5">
    <div class="row">
        <div class="col-md-3 mb-4">
            <nav class="list-group">
                <a href="{% url 'member-profile' %}" class="list-group-item list-group-item-action{% if request.resolver_match.url_name == 'member-profile' %} active{% endif %}">My Profile</a>
                <a href="{% url 'member-requests' %}" class="list-group-item list-group-item-action{% if request.resolver_match.url_name == 'member-requests' %} active{% endif %}">My Requests</a>
                <form method="post" action="{% url 'member-logout' %}" style="margin:0;">
                    {% csrf_token %}
                    <button type="submit" class="list-group-item list-group-item-action text-start border-0 bg-transparent">Log Out</button>
                </form>
            </nav>
        </div>
        <div class="col-md-9">
            {% block portal_content %}{% endblock %}
        </div>
    </div>
</div>
{% endblock %}
```

Create `blowcomotion/templates/member/profile.html`:

```html
{% extends "member/portal_base.html" %}
{% block title %}My Profile — Blowcomotion{% endblock %}
{% block portal_content %}
<h2 class="mb-4">My Profile</h2>
{% if messages %}{% for msg in messages %}<div class="alert alert-success">{{ msg }}</div>{% endfor %}{% endif %}
{% if member.pending_email %}
<div class="alert alert-info">
    A confirmation email has been sent to <strong>{{ member.pending_email }}</strong>. Click the link in that email to complete the change.
</div>
{% endif %}
<form method="post" enctype="multipart/form-data" id="member-form">
    {% csrf_token %}
    <input type="hidden" name="g-recaptcha-response" value="">

    <h5 class="mt-4 mb-3">Personal Information</h5>
    <div class="row g-3">
        <div class="col-md-4">
            <label class="form-label">First Name *</label>
            {{ form.first_name }}
            {% if form.first_name.errors %}<div class="text-danger small">{{ form.first_name.errors }}</div>{% endif %}
        </div>
        <div class="col-md-4">
            <label class="form-label">Last Name *</label>
            {{ form.last_name }}
            {% if form.last_name.errors %}<div class="text-danger small">{{ form.last_name.errors }}</div>{% endif %}
        </div>
        <div class="col-md-4">
            <label class="form-label">Preferred Name</label>
            {{ form.preferred_name }}
        </div>
        <div class="col-md-6">
            <label class="form-label">Email</label>
            {{ form.email }}
            {% if form.email.errors %}<div class="text-danger small">{{ form.email.errors }}</div>{% endif %}
            <div class="form-text">Changing your email requires confirmation. A link will be sent to the new address.</div>
        </div>
        <div class="col-md-6">
            <label class="form-label">Phone</label>
            {{ form.phone }}
        </div>
    </div>

    <h5 class="mt-4 mb-3">Address</h5>
    <div class="row g-3">
        <div class="col-12"><label class="form-label">Street Address</label>{{ form.address }}</div>
        <div class="col-md-4"><label class="form-label">City</label>{{ form.city }}</div>
        <div class="col-md-3"><label class="form-label">State</label>{{ form.state }}</div>
        <div class="col-md-2"><label class="form-label">Zip</label>{{ form.zip_code }}</div>
        <div class="col-md-3"><label class="form-label">Country</label>{{ form.country }}</div>
    </div>

    <h5 class="mt-4 mb-3">Birthday</h5>
    <div class="row g-3">
        <div class="col-md-4"><label class="form-label">Month</label>{{ form.birth_month }}</div>
        <div class="col-md-4"><label class="form-label">Day</label>{{ form.birth_day }}</div>
        <div class="col-md-4"><label class="form-label">Year</label>{{ form.birth_year }}</div>
    </div>

    <h5 class="mt-4 mb-3">Music</h5>
    <div class="row g-3">
        <div class="col-md-6"><label class="form-label">Primary Instrument</label>{{ form.primary_instrument }}</div>
        <div class="col-12">
            <label class="form-label">Additional Instruments</label>
            {{ form.additional_instruments }}
        </div>
    </div>

    <h5 class="mt-4 mb-3">About You</h5>
    <div class="mb-3"><label class="form-label">Bio</label>{{ form.bio }}</div>
    <div class="mb-3"><label class="form-label">What inspired you to join?</label>{{ form.inspired_by }}</div>
    <div class="mb-3"><label class="form-label">Emergency Contact</label>{{ form.emergency_contact }}</div>
    <div class="mb-3"><label class="form-label">Profile Photo</label>{{ form.image }}</div>

    <h5 class="mt-4 mb-3">Notification Preferences</h5>
    <div class="form-check mb-2">{{ form.notify_rental_updates }} <label class="form-check-label">Rental status updates</label></div>
    <div class="form-check mb-2">{{ form.notify_reminders }} <label class="form-check-label">Operational reminders</label></div>
    <div class="form-check mb-2">{{ form.notify_announcements }} <label class="form-check-label">Band announcements</label></div>

    <div class="mt-4">
        <button type="submit" class="site-btn">Save Profile</button>
    </div>
</form>
{% endblock %}

{% block extra_js %}
{{ block.super }}
{% if include_form_js %}
<script>
(function() {
    var form = document.getElementById('member-form');
    if (!form || typeof grecaptcha === 'undefined' || !window.RECAPTCHA_SITE_KEY) return;
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        var self = this;
        grecaptcha.ready(function() {
            grecaptcha.execute(window.RECAPTCHA_SITE_KEY, {action: 'submit'}).then(function(token) {
                self.querySelector('input[name="g-recaptcha-response"]').value = token;
                self.submit();
            }).catch(function() { self.submit(); });
        });
    });
})();
</script>
{% endif %}
{% endblock %}
```

Create `blowcomotion/templates/member/requests.html`:

```html
{% extends "member/portal_base.html" %}
{% block title %}My Requests — Blowcomotion{% endblock %}
{% block portal_content %}
<h2 class="mb-4">My Requests</h2>
<div class="alert alert-info">
    <strong>Coming soon.</strong> Your instrument rental requests will appear here once the rental system is updated.
</div>
{% endblock %}
```

Replace `blowcomotion/templates/member/confirm_email_result.html` with:

```html
{% extends "base.html" %}
{% block title %}Email Confirmation — Blowcomotion{% endblock %}
{% block content %}
<div class="container py-5 text-center">
    {% if confirmed %}
        <h1 class="mb-3">Email Confirmed</h1>
        <p class="lead">Your email address has been updated to <strong>{{ new_email }}</strong>.</p>
        <a href="{% url 'member-profile' %}" class="site-btn mt-3">Go to My Profile</a>
    {% elif expired %}
        <h1 class="mb-3">Link Expired</h1>
        <p>This confirmation link has expired. Please update your email again from your profile.</p>
        <a href="{% url 'member-profile' %}" class="site-btn mt-3">My Profile</a>
    {% else %}
        <h1 class="mb-3">Link Invalid</h1>
        <p>This confirmation link is invalid or has already been used.</p>
        <a href="{% url 'member-profile' %}" class="site-btn mt-3">My Profile</a>
    {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 6: Run portal tests**

```bash
python manage.py test blowcomotion.tests.test_member_portal -v 2
```

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add blowcomotion/member_views.py blowcomotion/member_forms.py blowcomotion/templates/member/ blowcomotion/tests/test_member_portal.py
git commit -m "feat: add member portal (profile edit, requests stub, email confirmation)"
```

---

### Task 10: Header Navigation

> **Parallel with Task 9 — start after Task 4 completes.**

**Files:**
- Modify: `blowcomotion/templates/header.html`

**Interfaces:**
- Consumes: URL names `member-login`, `member-logout`, `member-profile`

- [ ] **Step 1: Update header.html**

In `blowcomotion/templates/header.html`, find the closing `</div>` of `header__right__social` block (around line 46). Add the member login/logout controls after the social links div and before the closing `</div>` of `header__nav`:

```html
                    <div class="header__member-auth ms-3">
                        {% if request.user.is_authenticated and not request.user.is_staff %}
                            <a href="{% url 'member-profile' %}" class="site-btn site-btn--small">My Profile</a>
                            <form method="post" action="{% url 'member-logout' %}" style="display:inline;">
                                {% csrf_token %}
                                <button type="submit" class="site-btn site-btn--small site-btn--outline">Log Out</button>
                            </form>
                        {% elif not request.user.is_authenticated %}
                            <a href="{% url 'member-login' %}" class="site-btn site-btn--small site-btn--outline">Member Login</a>
                        {% endif %}
                    </div>
```

Specifically, insert it after line 46 (`</div>`) but before line 47 (`</div>`):

```html
                    {% if settings.blowcomotion.SiteSettings.facebook or settings.blowcomotion.SiteSettings.instagram %}
                        <div class="header__right__social">
                            ...
                        </div>
                    {% endif %}
                    <div class="header__member-auth ms-3">
                        {% if request.user.is_authenticated and not request.user.is_staff %}
                            <a href="{% url 'member-profile' %}" class="site-btn site-btn--small">My Profile</a>
                            <form method="post" action="{% url 'member-logout' %}" style="display:inline;">
                                {% csrf_token %}
                                <button type="submit" class="site-btn site-btn--small site-btn--outline">Log Out</button>
                            </form>
                        {% elif not request.user.is_authenticated %}
                            <a href="{% url 'member-login' %}" class="site-btn site-btn--small site-btn--outline">Member Login</a>
                        {% endif %}
                    </div>
                </div>  {# closes header__nav #}
```

- [ ] **Step 2: Smoke test — start dev server and verify header**

```bash
python manage.py runserver
```

Visit `http://localhost:8000/` — header should show "Member Login" link when not logged in.

Log in at `http://localhost:8000/member/login/` with any admin user — header should show "My Profile" + "Log Out" for non-staff users.

- [ ] **Step 3: Commit**

```bash
git add blowcomotion/templates/header.html
git commit -m "feat: add member login/logout/My Profile links to site header"
```

---

## Self-Review

### Spec coverage check

| Spec requirement | Task |
|---|---|
| `user` OneToOneField on Member | Task 2 |
| `pending_email`, `notify_*` fields | Task 2 |
| `PasswordSetToken` model | Task 2 |
| `EmailChangeToken` model | Task 2 |
| Argon2 password hashing | Task 1 |
| `create_member_user` helper | Task 3 |
| `send_set_password_email` helper | Task 3 |
| `send_email_change_confirmation` helper | Task 3 |
| Login view with reCAPTCHA + honeypot | Task 4 |
| `django-axes` login rate limiting | Task 1 (config) + Task 4 (applied automatically via backend) |
| Set-password view (valid/expired/used/superseded token) | Task 4 |
| `MemberPasswordResetView` (custom form_valid) | Task 4 |
| Get-access view | Task 4 |
| Django LogoutView | Task 4 |
| `django-ratelimit` on set-password, get-access, password-reset request | Task 4 |
| Auto-logout middleware (non-staff only, 60-min idle) | Task 5 |
| `invite_members` command with --dry-run, --member-id | Task 6 |
| Member signup → create user + send set-password email | Task 7 |
| `Member.save()` email drift guard | Task 2 + Task 8 |
| Profile edit (all non-admin fields) | Task 9 |
| Email change → pending_email + confirmation flow | Task 9 |
| My Requests stub | Task 9 |
| Confirm-email view | Task 9 |
| Header login/logout/My Profile | Task 10 |
| Wagtail URL routing (member before wagtail_urls) | Task 4 (urls.py) |
| SESSION_COOKIE_SECURE in production | Task 1 |
| SESSION_COOKIE_HTTPONLY, SAMESITE | Task 1 |
| Audit logging (logger.info on key events) | Tasks 3, 4, 6, 9 |
| Accessibility: labeled errors, keyboard-accessible | All form templates (Task 4, 9) |

All spec requirements covered. ✓
