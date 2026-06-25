---
name: migration
description: Create and validate Django migrations safely for the blowcomotion project
disable-model-invocation: true
---

Run these steps in order. Stop and report if any step fails.

## 1. Detect pending changes

```bash
python manage.py makemigrations --check --dry-run
```

If this exits 0, there are no pending model changes — confirm with the user before continuing.

## 2. Generate the migration

```bash
python manage.py makemigrations
```

Open the generated migration file and check:
- Any `RunPython` operations have a `reverse_code` argument (or `atomic=False` if truly irreversible)
- `StreamField` changes preserve existing block types — removing a block type silently drops data
- New non-nullable fields have a `default` or `migrations.AddField` with `preserve_default=False`
- The migration does not reference Wagtail's internal content types directly (use model references instead)

## 3. Apply locally

```bash
python manage.py migrate
```

If this fails, do NOT delete the migration file. Fix the underlying model issue first.

## 4. Verify the test suite still passes

```bash
python manage.py test
```

CI runs migrations on a fresh database — a migration that applies on top of existing data can still fail on a clean schema.

## 5. Squashing (optional)

Only squash if there are >20 unapplied migrations in an app. Run:
```bash
python manage.py squashmigrations blowcomotion <first> <last>
```
Then delete the original files only after verifying the squash applies cleanly.
