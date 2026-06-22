# Member Authentication & Profile Management Design

**Issues:** #212 (Member self-service upgrade), #183 (Member profile edit)  
**Date:** 2026-06-21  
**Status:** Approved

---

## Overview

Add a member authentication system and self-service profile portal to blowcomotion.org. Members get Django `User` accounts linked to their existing `Member` records via a `OneToOneField`. Authentication uses Django's built-in views and token system with custom templates. The portal covers profile editing and a stub for the future rental requests dashboard (#157).

---

## Data Model

### `Member` model changes

Add to the existing `Member` model in `blowcomotion/models.py`:

```python
user = OneToOneField(
    settings.AUTH_USER_MODEL,
    null=True, blank=True,
    on_delete=SET_NULL,
    related_name="member"
)
pending_email = EmailField(null=True, blank=True)
notify_rental_updates = BooleanField(default=True)
notify_reminders = BooleanField(default=True)
notify_announcements = BooleanField(default=True)
```

The `user` field is nullable so existing members continue to work without an account until they claim one. `Member.email` is the source of truth — `User.email` is populated at account creation and kept in sync on email change.

`pending_email` stores a requested email address change that has not yet been confirmed. It is set when the member submits a new email on the profile form and cleared once they click the confirmation link. The existing `Member.email` (and `User.email`) remain unchanged until confirmation.

`User.username` is set to the member's email address at account creation time. On confirmed email change, `User.username` and `User.email` are both updated to match `Member.email`.

### New `PasswordSetToken` model

```python
class PasswordSetToken(Model):
    member = ForeignKey(Member, on_delete=CASCADE, related_name="set_password_tokens")
    uuid = UUIDField(default=uuid4, unique=True)
    created_at = DateTimeField(auto_now_add=True)
    used = BooleanField(default=False)
    superseded = BooleanField(default=False)
```

Generating a new token for a member marks all prior unused tokens for that member as `superseded=True`. Token is valid if `used=False`, `superseded=False`, and `created_at` is within 24 hours.

### New `EmailChangeToken` model

```python
class EmailChangeToken(Model):
    member = ForeignKey(Member, on_delete=CASCADE, related_name="email_change_tokens")
    uuid = UUIDField(default=uuid4, unique=True)
    new_email = EmailField()
    created_at = DateTimeField(auto_now_add=True)
    used = BooleanField(default=False)
```

When the member submits a new email on the profile form, an `EmailChangeToken` is created (prior unused tokens for this member are invalidated) and a confirmation email is sent to `new_email` with a link to `/member/confirm-email/<uuid>/`. On confirmation: validate token (unused, under 24 hours); update `Member.email`, `Member.pending_email = None`, `User.email`, and `User.username`; mark token used.

---

## Authentication Flows

### Set Password (new account claim)

1. A `User` with unusable password is created and linked to `Member`.
2. A `PasswordSetToken` is generated; prior tokens for this member are marked superseded.
3. An email is sent to the member's address containing the direct link: `/member/set-password/<uuid>/`.
4. On form submission: validate token (unused, not superseded, under 24 hours); set password; mark token used; log the member in.

Email copy: "Welcome to Blowcomotion — set your password to access your member profile." Email includes the direct link to the set-password form.

### Login

- URL: `/member/login/`
- Django's `LoginView` with a custom template.
- reCAPTCHA (consistent with existing site forms).
- JS honeypot field (consistent with existing site forms).
- Rate-limited via `django-axes`: lockout after 5 failed attempts per IP for 30 minutes.
- "Forgot password?" link on the form.
- "New member? Get access →" link to `/member/get-access/`.

### Forgot Password / Reset

- URLs: `/member/password-reset/`, `/member/password-reset/confirm/<uidb64>/<token>/`
- `MemberPasswordResetView` subclasses Django's `PasswordResetView`, overriding `form_valid` to handle two cases before falling through to the default reset behaviour:
  - If the email matches an active `Member` with no `User` (or a `User` with an unusable password): creates the `User` if needed and sends a Set Password email instead of a reset email.
  - If no active `Member` is found for the email: shows a generic "if you're a member, check your email" response without sending anything (no enumeration).
- `PasswordResetConfirmView` is used as-is with a custom template.
- reCAPTCHA on the request form.
- Reset email includes the direct link to the reset form.
- Tokens are single-use and expire after 24 hours (Django's default token generator).

### Logout

- Django's `LogoutView` via POST (CSRF-protected).
- Calls `session.flush()` to fully invalidate the server-side session.
- Login/logout buttons in the site header: login shown when anonymous, "My Profile" + logout shown when authenticated.

### Auto-logout

- Idle timeout applied only to member (non-staff) sessions. Rather than setting the global `SESSION_COOKIE_AGE` (which would also shorten Wagtail admin sessions), a lightweight middleware checks `request.session["last_activity"]` on each request for non-staff users and calls `session.flush()` + redirects to login if more than 60 minutes have elapsed. `last_activity` is updated on each request.
- A JS snippet warns the member 5 minutes before the 60-minute mark with an option to extend (any page interaction resets the timer via the middleware).

### Get Access (on-demand account creation)

- URL: `/member/get-access/`
- Email input form with reCAPTCHA.
- If email matches an active `Member` with no `User`: creates the account, sends Set Password email.
- If email matches a `Member` with an existing `User`: sends a standard password reset email.
- If no match: shows generic "if you're a member, check your email" response.

---

## Member Portal

Base URL: `/member/` — requires login.

### Profile Edit (`/member/profile/`)

A single form covering all non-admin `Member` fields:

- Preferred name, first name, last name
- Email (triggers verification email to new address; old email stays active until confirmed)
- Phone
- Address, city, state, zip code, country
- Birthday (month, day, year)
- Emergency contact
- Bio
- Inspired by
- Primary instrument
- Additional instruments
- Profile image

Notification preferences rendered as a section within this form:
- `notify_rental_updates` — Rental status updates
- `notify_reminders` — Operational reminders
- `notify_announcements` — Band announcements

reCAPTCHA on submit. Saves to `Member`; keeps `User.email` in sync on email change.

### My Requests (`/member/requests/`)

Stub page with a "Coming soon" notice. Nav link is wired and functional. No data queried. Reserved for instrument rental dashboard work in #157.

### Navigation

Login/logout and "My Profile" link in the site header. Members have `is_staff=False` — the member portal is completely isolated from the Wagtail admin.

---

## Bulk Invite & Onboarding

### Management command: `invite_members`

Targets all active `Member` records without a linked `User`. For each eligible member:

1. Create a `User` (unusable password), link to `Member`.
2. Generate a `PasswordSetToken`.
3. Send the set-password email with the direct link.

Flags:
- `--dry-run` — prints who would be invited, sends nothing.
- `--member-id <id>` — processes a single member (for testing).

Safe to re-run — members who already have an account are skipped. Logs a summary at the end (invited / skipped / errored).

### New member signup

After `_process_member_signup()` creates a `Member`, it immediately creates the linked `User` and fires the set-password email. Email copy: "Welcome to Blowcomotion — set your password to access your member profile." Email includes the direct link to the set-password form.

---

## Security

### Password hashing

Argon2 via `django[argon2]` added to `requirements.txt`. Django's existing `AUTH_PASSWORD_VALIDATORS` remain in place.

### Rate limiting

`django-axes` added. Locks out after 5 failed login attempts per IP for 30 minutes. Applied to login, set-password, and get-access forms.

### Token security

`PasswordSetToken` is single-use, expires in 24 hours, and new tokens supersede prior unused tokens. Django's built-in `PasswordResetTokenGenerator` provides the same guarantees for reset tokens natively.

### Audit logging

Key events logged via Django's standard `logging` (consistent with existing log config):

- Set-password link sent
- Set-password completed
- Login success / failure
- Logout
- Password reset requested / completed

### Session security

```python
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True   # production only
SESSION_COOKIE_SAMESITE = "Lax"
```

Session invalidated server-side on logout via `session.flush()`.

---

## New Dependencies

| Package | Purpose |
|---|---|
| `django[argon2]` | Argon2 password hashing |
| `django-axes` | Login rate limiting / lockout |

---

## URL Summary

| URL | View | Auth required |
|---|---|---|
| `/member/login/` | Django `LoginView` | No |
| `/member/logout/` | Django `LogoutView` (POST) | Yes |
| `/member/set-password/<uuid>/` | Custom set-password view | No |
| `/member/get-access/` | Custom get-access view | No |
| `/member/password-reset/` | Django `PasswordResetView` | No |
| `/member/password-reset/confirm/<uidb64>/<token>/` | Django `PasswordResetConfirmView` | No |
| `/member/` | Portal home (redirect to profile) | Yes |
| `/member/profile/` | Profile edit view | Yes |
| `/member/requests/` | My Requests stub | Yes |
| `/member/confirm-email/<uuid>/` | Email change confirmation | No |

---

## Testing

In `blowcomotion/tests/`:

**Model tests**
- `User` ↔ `Member` OneToOne link
- Token creation, expiry (>24h), used flag, superseding prior tokens
- Notification preference defaults

**View tests**
- Login / logout
- Set-password: valid token, expired token, used token, superseded token
- Forgot password: member with account, member without account, unknown email (no enumeration)
- Get-access: no account → creates and sends; existing account → reset email; unknown → generic response
- Profile edit: email change sets `pending_email` and sends verification email; confirming link updates `Member.email`, `User.email`, and `User.username`, and clears `pending_email`; all other non-admin fields save correctly
- Portal pages require login (redirect to login if anonymous)

**Management command tests**
- `invite_members` dry-run produces no side effects
- Already-linked members are skipped
- `--member-id` processes only that member
- Error on one member does not abort the rest

**Security tests**
- Rate limiting triggers lockout after 5 failures
- Token enumeration returns generic response
- Session is fully invalidated on logout
- Expired / used / superseded tokens are rejected
