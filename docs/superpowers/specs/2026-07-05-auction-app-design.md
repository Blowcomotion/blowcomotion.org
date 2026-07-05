# Silent Auction App — Design Spec

**Issue:** [#116 Silent auction bidding](https://github.com/Blowcomotion/blowcomotion.org/issues/116)
**Date:** 2026-07-05
**Status:** Approved pending user review

## Purpose

Run silent auctions for fundraisers (next: fall 2026). Auctioneers upload items
with images, starting bids, and increments; the public views items, bids, and
gets outbid/winner notifications by email and (opt-in) SMS via Twilio. Winners
and backup winners are picked automatically at the deadline. The whole thing
resets cleanly per event and expired auctions render as historical results.
Scale target: up to 100 items per auction (~12 typical).

## Decisions made during design (with Nick)

1. **Presentation:** StreamField `AuctionBlock` placed on CMS pages (e.g. the
   fundraiser page), NOT a views-only portal and NOT items-as-StructBlocks
   (bids need FK targets, so items must be DB rows). App views handle item
   detail, bid POSTs, and the Twilio webhook.
2. **Bidder identity:** name + email + phone registration on first bid, no
   passwords. Signed cookie remembers the bidder; re-entering the same
   email + phone on another device retrieves the same account/bids (help text
   states this).
3. **Notifications:** email always; SMS only for bidders who opted in.
   Bidders can bid back via SMS reply: `BID <item#> <amount>`, plus `HELP`.
   Auth for inbound SMS = Twilio `From` number matched to registered bidder.
4. **Payments:** out of scope. Winner notification includes per-auction
   `payment_instructions` text (pay at pickup).
5. **Anti-sniping:** optional per-auction soft close, off by default, with
   help text.
6. **Backup winner:** silent — stored and shown in admin; Auctioneer manually
   promotes if the winner flakes, which then notifies the backup.
7. **Admin UI:** Wagtail snippets gated by a new Auctioneer group.
8. **Dev gating:** Wagtail native page privacy ("visible to group: Auctioneer")
   on the CMS page hosting the block; flipped public at launch. No custom code.

## Architecture

New `auction` Django app with its **own `models.py` and migrations** (allowed
for new domains per CLAUDE.md — no existing production data). It contains
models, snippet viewsets + chooser, the `AuctionBlock`, views, urls
(mounted at `/auction/` above the Wagtail catch-all), templates, sms/email
helpers, management command, and tests. `blowcomotion/blocks/__init__.py`
re-exports `AuctionBlock`; `BlankCanvasPage` gains it as a block type.

## Data model

- **Auction** (ClusterableModel, snippet): `name`, `description`,
  `close_time`, `soft_close_enabled` (default False, help text explains
  bids in the final window extend that item's clock),
  `soft_close_minutes` (default 5), `payment_instructions` (included in
  winner notices), `created_at`. "Open" = `close_time` in the future.
  Reset per event = create a new Auction; old rows are the history.
- **AuctionItem** (Orderable inline under Auction): `auction` FK, `number`
  (positive int, unique per auction — used on printed cards and in SMS
  commands), `title`, `description`, `starting_bid`, `bid_increment`,
  `close_time` (nullable; falls back to auction's, extended by soft close),
  `winning_bid` / `backup_bid` (nullable FKs to Bid), `winner_notified_at`
  (idempotency marker for close processing).
- **AuctionItemImage** (Orderable inline under AuctionItem): FK to Wagtail
  image + sort order. One or more images per item → carousel on the detail
  page, first image on the grid card. The 7 saved merchant icons are usable
  directly.
- **Bidder**: `auction` FK (registration is per event), `name`, `email`,
  `phone` (normalized to E.164 on save so Twilio `From` matching works),
  `sms_opt_in`. Unique together (auction, phone) and (auction, email).
- **Bid**: `item` FK, `bidder` FK, `amount` (Decimal), `source`
  (`web`/`sms`), `created_at`. Created inside a transaction with
  `select_for_update()` on the item; validation: item open; first bid must
  be ≥ `starting_bid`, subsequent bids ≥ current top bid + `bid_increment`.

## Auctioneer role

Extend the existing `setup_roles` management command with an **Auctioneer**
group: Wagtail admin access + add/change/delete/view on Auction, AuctionItem,
AuctionItemImage, Bidder, Bid (perms live in the `auction` app namespace).
Same recipe as Attendance Taker. Auctioneers log into Wagtail admin and see
only auction models.

## Bidding flow (web)

- `AuctionBlock` (SnippetChooserBlock for Auction + optional intro heading)
  renders the item grid: image, title, current bid, bid count, closes-at,
  item `#number`. Cards link to the item detail view.
- Item detail view (`/auction/<auction_id>/item/<number>/`): image carousel,
  description, bid history (bidders displayed as "First L."), bid form.
- First bid on a device: form includes name, email, phone, SMS opt-in
  checkbox, amount. Success sets a signed `auction_bidder` cookie; later
  bids are amount-only. Help text on the registration form: "Already
  registered on another device? Enter the same email and phone to continue
  bidding as the same person." Matching email+phone reattaches the cookie.
- Grid and detail auto-refresh prices via htmx polling; both show
  "Last refreshed: HH:MM:SS" and a **Refresh now** button (htmx trigger on
  the same partial).
- reCAPTCHA per house rules: bid/registration POSTs call
  `_validate_recaptcha(request)` first; forms carry `data-recaptcha` and the
  page loads `form.js` (no inline submit handlers). Standard disclosure
  notice appears automatically.
- Soft close: if enabled and a valid bid lands within `soft_close_minutes`
  of the item's effective close time, item `close_time` is pushed to
  now + `soft_close_minutes`.

## Notifications

Outbound (module `auction/notifications.py`):
- **Outbid**: previous top bidder gets email always + SMS if opted in.
  Text: `You've been outbid on #12 Yeti Cooler — now $55. Reply BID 12 60
  to retake the lead, or see it here: <item URL>`.
- **Winner**: at close, winner gets email + SMS with amount, item link, and
  the auction's `payment_instructions`. Backup gets nothing unless promoted.
- Email goes through `_MemberEmail` (FORM_TEST_EMAIL copy is centralized
  there — confirmed this covers bidder-facing mail too). The winner-closing
  management command path must include its own FORM_TEST_EMAIL copy if it
  sends via `send_mail` directly — prefer routing it through the same
  notifications module so there is exactly one send path.
- SMS via Twilio REST API. Settings in `local.py`:
  `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` —
  `getattr(settings, ..., None)` pattern; if unset, SMS is skipped silently
  (Patreon-style) and email still flows. Add `twilio` to requirements.txt.

Inbound (`/auction/sms/` POST, csrf-exempt, **X-Twilio-Signature validated**
— reject on mismatch):
- Match `From` to a Bidder in the most recent auction with any open item;
  unknown numbers get a "register on the website first" reply.
- `BID <item#> <amount>` → same validated bid path as web (source=`sms`).
  Replies confirm success, or explain the failure (too low → states minimum,
  unknown item, item closed).
- `HELP` or unparseable input → usage text. STOP/START are handled by
  Twilio's native opt-out; treat delivery failures as non-fatal.

## Winner processing / historical

Management command `close_auction_items`: for each item whose effective close
time has passed and `winner_notified_at` is null (row-locked), set
`winning_bid` = top bid, `backup_bid` = highest bid by a different bidder,
notify the winner, stamp `winner_notified_at`. Items with no bids just close.

Triggers, belt and suspenders:
1. **Lazy**: auction page/detail views invoke the same closing routine for
   expired items of the viewed auction (instant during a live event,
   idempotent thanks to the stamp + lock).
2. **Cron backstop**: hourly PythonAnywhere scheduled task runs the command
   (`sync_gigs` pattern).

Closed items leave the live grid and render in a "Completed" section with
winner first names. An `AuctionBlock` pointing at a fully-closed auction
renders as pure results — that's the historical auctions page, no second
block or template needed.

**Promote backup**: Auctioneer action in Wagtail admin on the item; sets
`winning_bid` = `backup_bid`, clears backup, re-notifies. After close, the
Auctioneer also gets a summary email (items, winners, amounts, totals).

## Testing

`auction/tests/` mirroring `members/tests/` (factory helpers, TestCase):
- models: bid validation, increments, first-bid vs subsequent, soft-close
  extension, phone normalization, unique constraints
- views: registration+bid, cookie reattach, recaptcha required, refresh
  partials, closed-item rejection
- sms: signature rejection, BID parsing (good/low/unknown item/closed/
  unknown number), HELP fallback
- command: winner + backup selection, idempotency, no-bid items, Twilio and
  email mocked, FORM_TEST_EMAIL copy asserted

## Out of scope

Payments/checkout, bidder accounts/passwords, auto-promotion claim windows,
LIST/STATUS SMS commands, live websockets (htmx polling suffices).

## Ops flags (not code)

- **Start Twilio A2P 10DLC (or toll-free) registration now** — approval can
  take weeks; the fall date doesn't wait for it.
- Add hourly `close_auction_items` task on PythonAnywhere at deploy time.
- Seed data for dev: items from the fall-2025 fundraiser page with made-up
  prices, per Beej's comment.
