import csv
import os
import re
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from blowcomotion.models import Instrument, Member


class Command(BaseCommand):
    help = "Load members from a CSV file into the Member database table."

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_path",
            help="Absolute or relative path to the member CSV export.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate the import and report the summary without writing to the database.",
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="Update an existing member when a record with the same first and last name already exists.",
        )

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        dry_run = options["dry_run"]
        allow_updates = options["update"]

        if not os.path.exists(csv_path):
            raise CommandError(f"CSV file not found: {csv_path}")

        created_count = 0
        updated_count = 0
        skipped_count = 0
        error_count = 0
        missing_instruments = set()

        instrument_cache = self._build_instrument_cache()

        with open(csv_path, newline="", encoding="utf-8-sig") as csvfile:
            reader = csv.DictReader(csvfile)

            if not reader.fieldnames:
                raise CommandError("The provided CSV file is empty or missing a header row.")

            required_headers = {"first_name", "last_name"}
            missing_headers = required_headers - set(h.lower() for h in reader.fieldnames)
            if missing_headers:
                raise CommandError(
                    "CSV file is missing required columns: "
                    + ", ".join(sorted(missing_headers))
                )

            for index, row in enumerate(reader, start=2):  # start=2 for row number including header
                try:
                    cleaned_row = self._normalize_row(row)
                except ValueError as exc:
                    error_count += 1
                    self.stderr.write(
                        self.style.ERROR(f"Row {index}: {exc}. Skipping.")
                    )
                    continue

                first_name = cleaned_row["first_name"]
                last_name = cleaned_row["last_name"]

                if not first_name or not last_name:
                    skipped_count += 1
                    self.stderr.write(
                        self.style.WARNING(
                            f"Row {index}: Missing first or last name. Skipping."
                        )
                    )
                    continue

                primary_instrument = None
                instrument_name = cleaned_row.pop("instrument_name", None)
                if instrument_name:
                    primary_instrument, warning = self._resolve_instrument(
                        instrument_name,
                        instrument_cache,
                    )
                    if warning:
                        missing_instruments.add(instrument_name)
                        self.stderr.write(
                            self.style.WARNING(f"Row {index}: {warning}")
                        )

                member_defaults = {
                    **cleaned_row,
                    "primary_instrument": primary_instrument,
                }

                existing_member = Member.objects.filter(
                    first_name__iexact=first_name,
                    last_name__iexact=last_name,
                ).first()

                if existing_member:
                    if not allow_updates:
                        skipped_count += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"Row {index}: Member '{first_name} {last_name}' already exists. Use --update to overwrite."
                            )
                        )
                        continue

                    for field, value in member_defaults.items():
                        setattr(existing_member, field, value)

                    try:
                        self._save_member(existing_member, dry_run)
                    except Exception as exc:  # noqa: BLE001
                        error_count += 1
                        self.stderr.write(
                            self.style.ERROR(
                                f"Row {index}: Failed to update '{existing_member}'. Error: {exc}"
                            )
                        )
                        continue

                    updated_count += 1
                else:
                    new_member = Member(**member_defaults)

                    try:
                        self._save_member(new_member, dry_run)
                    except Exception as exc:  # noqa: BLE001
                        error_count += 1
                        self.stderr.write(
                            self.style.ERROR(
                                f"Row {index}: Failed to create member '{first_name} {last_name}'. Error: {exc}"
                            )
                        )
                        continue

                    created_count += 1

        summary_parts = [
            f"Created: {created_count}",
            f"Updated: {updated_count}",
            f"Skipped: {skipped_count}",
            f"Errors: {error_count}",
        ]
        mode = "DRY RUN" if dry_run else "IMPORT"
        self.stdout.write(self.style.SUCCESS(f"{mode} complete. {' | '.join(summary_parts)}"))

        if missing_instruments:
            missing_list = ", ".join(sorted(missing_instruments))
            self.stdout.write(
                self.style.WARNING(
                    "Instruments not found (records imported without a primary instrument): "
                    + missing_list
                )
            )

    def _normalize_row(self, row):
        """Return a dict of cleaned values ready for Member instantiation."""
        def get_value(key):
            for candidate in (key, key.lower(), key.upper()):
                if candidate in row and row[candidate] is not None:
                    return row[candidate].strip()
            return ""

        def parse_bool(value, default=False):
            if value is None:
                return default
            normalized = value.strip().lower()
            if normalized in {"yes", "y", "true", "1"}:
                return True
            if normalized in {"no", "n", "false", "0"}:
                return False
            return default

        def parse_int(value):
            if not value:
                return None
            try:
                return int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid integer '{value}'") from exc

        def parse_date(value):
            if not value:
                return None
            try:
                return datetime.strptime(value, "%m/%d/%Y").date()
            except ValueError as exc:
                raise ValueError(f"Invalid date '{value}' (expected MM/DD/YYYY)") from exc

        cleaned = {
            "first_name": get_value("first_name"),
            "last_name": get_value("last_name"),
            "preferred_name": get_value("preferred_name") or None,
            "bio": get_value("bio") or None,
            "email": get_value("email") or None,
            "phone": get_value("phone") or None,
            "address": get_value("address") or None,
            "city": get_value("city") or None,
            "state": get_value("state") or None,
            "zip_code": get_value("zip_code") or None,
            "country": get_value("country") or None,
            "notes": get_value("notes") or None,
            "emergency_contact": get_value("emergency_contact") or None,
        }

        cleaned["birth_month"] = parse_int(get_value("birth_month"))
        cleaned["birth_day"] = parse_int(get_value("birth_day"))
        cleaned["birth_year"] = parse_int(get_value("birth_year"))
        cleaned["join_date"] = parse_date(get_value("join_date"))
        cleaned["last_seen"] = parse_date(get_value("last_seen"))
        cleaned["separation_date"] = parse_date(get_value("separation_date"))

        cleaned["is_active"] = parse_bool(get_value("is_active"), default=False)
        cleaned["instructor"] = parse_bool(get_value("instructor"), default=False)
        cleaned["board_member"] = parse_bool(get_value("board_member"), default=False)
        cleaned["renting"] = parse_bool(get_value("Renting"), default=False)

        instrument_value = get_value("instruments")
        cleaned["instrument_name"] = instrument_value or None

        return cleaned

    def _save_member(self, member, dry_run=False):
        member.full_clean()
        if dry_run:
            return member
        with transaction.atomic():
            member.save()
        return member

    def _build_instrument_cache(self):
        instruments = list(Instrument.objects.all())
        exact_lookup = {instrument.name.lower(): instrument for instrument in instruments}
        token_sets = [(instrument, self._normalize_tokens(instrument.name)) for instrument in instruments]
        return {
            "exact": exact_lookup,
            "token_sets": token_sets,
        }

    def _resolve_instrument(self, instrument_name, cache):
        name = instrument_name.strip()
        if not name:
            return None, ""

        lower_name = name.lower()
        exact_match = cache["exact"].get(lower_name)
        if exact_match:
            return exact_match, ""

        csv_tokens = self._normalize_tokens(name)
        if not csv_tokens:
            return None, f"Could not interpret instrument '{instrument_name}'. Leaving blank."

        subset_matches = [
            instrument
            for instrument, tokens in cache["token_sets"]
            if csv_tokens.issubset(tokens) and tokens
        ]
        if len(subset_matches) == 1:
            return subset_matches[0], ""
        if len(subset_matches) > 1:
            match_names = ", ".join(sorted(inst.name for inst in subset_matches))
            return None, (
                f"Instrument '{instrument_name}' matched multiple instruments ({match_names}). Leaving blank."
            )

        overlap_matches = [
            instrument
            for instrument, tokens in cache["token_sets"]
            if csv_tokens & tokens and tokens
        ]
        if len(overlap_matches) == 1:
            return overlap_matches[0], ""
        if len(overlap_matches) > 1:
            match_names = ", ".join(sorted(inst.name for inst in overlap_matches))
            return None, (
                f"Instrument '{instrument_name}' matched multiple instruments ({match_names}). Leaving blank."
            )

        return None, f"Could not find instrument '{instrument_name}'. Leaving blank."

    def _normalize_tokens(self, name):
        tokens = [
            token
            for token in re.split(r"[^\w]+", name.lower())
            if token
        ]
        return frozenset(tokens)
