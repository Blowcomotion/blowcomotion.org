# Member Profile Revision Logging

**Date:** 2026-06-23  
**Status:** Approved

## Problem

When a member edits their own profile at `/member/profile`, no audit trail is recorded. Admins have no way to see what changed, when, or who made the change.

## Goal

Record a full Wagtail revision snapshot each time a member successfully saves their profile, surfaced in the existing Wagtail admin history page at `/admin/snippets/blowcomotion/member/history/<pk>/`.

## Design

### 1. Add `RevisionMixin` to `Member`

`Member` currently extends `ClusterableModel, index.Indexed`. Adding `RevisionMixin` gives it Wagtail's built-in revision capability.

```python
class Member(RevisionMixin, ClusterableModel, index.Indexed):
```

`RevisionMixin` adds a `latest_revision` FK field, requiring one migration.

The revision JSON will include `MemberInstrument` children because they use `ParentalKey` and are part of the cluster.

### 2. Call `save_revision()` in `profile_view`

After a successful save — specifically after `additional_instruments` are rebuilt so the snapshot captures the full state — call:

```python
instance.save_revision(user=request.user, log_action="wagtail.edit")
```

This is placed after the `additional_instruments` delete/recreate loop and before the redirect.

### 3. Migration

Run `makemigrations` to generate the migration for the `latest_revision` FK field that `RevisionMixin` adds to `Member`.

## What this does NOT change

- No new models
- No new templates
- No new admin configuration
- No member-facing UI (history is admin-only for now)
- The existing history page at `/admin/snippets/blowcomotion/member/history/<pk>/` works automatically once `RevisionMixin` is present

## Files changed

- `blowcomotion/models.py` — add `RevisionMixin` to `Member` class signature
- `blowcomotion/member_views.py` — call `save_revision()` in `profile_view` after instruments rebuild
- `blowcomotion/migrations/XXXX_member_revision_mixin.py` — generated migration
