---
name: run-app
description: Launch the Django dev server and drive it in a headless browser (Playwright + system Chrome) to verify changes end-to-end, including logged-in member portal and Wagtail admin flows
---

# Run and drive blowcomotion.org in a browser

Verified working on macOS with pyenv python3 (Django env is global — no venv activation needed) and Playwright's `channel="chrome"` (system Google Chrome, no browser download).

## Launch

```bash
(python3 manage.py runserver 8123 --noreload > /tmp/blowco-server.log 2>&1 & echo $! > /tmp/blowco-server.pid)
for i in {1..30}; do curl -sf http://localhost:8123/ >/dev/null && break; sleep 1; done
```

Stop: `kill $(cat /tmp/blowco-server.pid)`.

- macOS has no `timeout` command — use the `for` loop above.
- **Capture stdout to a log file**: dev uses the console email backend, so the server log is how you intercept emails (login links, set-password links, form notifications). Emails start at `Subject:` lines; extract links with a regex like `http://localhost:8123/member/login/link/[^\s"'<>]+`.
- reCAPTCHA is skipped when no keys are in `local.py` (the default locally), so form POSTs work without tokens.

## Seed and clean up test data

Prefix everything `e2e.` so cleanup is a filter. Via `python3 manage.py shell -c` or a script piped to `shell`:

- Member with password: create `Member(first_name=..., email='e2e.member@example.com')`, save (auto-creates the linked User), then `m.user.set_password(...); m.user.save()`. Username == email.
- Wagtail admin: `User.objects.get_or_create(username='e2e_admin', ...)` with `is_staff=is_superuser=True` + password. Don't give it a Member row.
- Cleanup: **delete Members before their Users** — `Member.user` is `on_delete=PROTECT`, so deleting a linked User raises `ProtectedError`. Scope every delete with an `e2e.` filter; never `.all().delete()`.

## Drive

Playwright sync API, `pw.chromium.launch(channel="chrome", headless=True)`. Representative logged-in flows:

```python
# Wagtail admin login
page.goto("http://localhost:8123/admin/login/")
page.fill("#id_username", "e2e_admin"); page.fill("#id_password", "...")
page.click("button[type=submit]")

# Member portal login (password): /member/login/, fields #id_username (email) / #id_password
# Member portal login (magic link): POST email to the form[data-recaptcha] on /member/login/,
#   regex the link out of the server log, page.goto(link) -> auto-submits and lands on /member/profile/
```

Use separate `browser.new_context()` per identity (anonymous / member / admin) — contexts don't share cookies.

## Gotchas hit in practice

- **Public CMS forms** (`/join/`, `/booking/`, `/donate/`, contact) match `form[hx-post*='process-form'], form[action*='process-form']`. They contain **required `<select>` elements** — HTML5 validation silently blocks submit if you only fill text inputs. Select a non-empty option in every `select` first. Confirm submission by counting `"POST /process-form` lines in the server log, not by page content (htmx swap).
- **Wagtail members list** (`/admin/snippets/blowcomotion/member/`) is paginated and alphabetized — assert via the search box (`?q=<name>`), not page-1 content.
- **Wagtail page preview** for template checks: `/admin/pages/<id>/view_draft/` (homepage id is 3) serves with `request.is_preview=True`.
- End every run by grepping the server log for `Internal Server Error` — a flow can look fine in the browser while a background request 500s.
