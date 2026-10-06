"""
Phase 1 Task B — seed-pack loader. Idempotent: matches on each object's
natural/stable code, creates what's missing, and only updates a row if it
still looks exactly like what THIS pack last wrote there (tracked via
SeedRecord's checksum) — an admin's own edit is never silently overwritten.

This is intentionally a simpler, pack-name-dispatched implementation
rather than the fully generic "any model, any pack" engine the Master
Prompt describes in the abstract — see PHASE1_REPORT.md for why that
trade-off was made for this phase. Adding a new pack means adding one
`_apply_<pack_name>` method here; the idempotency/checksum machinery
(`_apply_row`) is already fully generic and reusable for any future pack.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.platform_core.models import (
    Country, Currency, LookupType, LookupValue, SeedRecord, Timezone,
)

PACKS_DIR = Path(__file__).resolve().parent.parent.parent / 'seed_packs'


def _jsonable(value):
    """Best-effort conversion so checksums never choke on a model instance,
    Decimal, date, etc. passed in `defaults` — natural keys are excluded
    from the checksum entirely (see _apply_row), so this only ever needs
    to handle plain `defaults` values."""
    if hasattr(value, 'pk'):
        return f'<fk:{value.pk}>'
    return str(value)


def _checksum(data: dict) -> str:
    safe = {k: _jsonable(v) for k, v in data.items()}
    return hashlib.sha256(json.dumps(safe, sort_keys=True).encode('utf-8')).hexdigest()


class Command(BaseCommand):
    help = 'Load a versioned seed pack (apps/platform_core/seed_packs/<name>.json). Idempotent — never overwrites an admin edit.'

    def add_arguments(self, parser):
        parser.add_argument('name', type=str, help='Pack name, e.g. core_geo, core_lookups, india_core')
        parser.add_argument('--dry-run', action='store_true', help='Report what would change without writing anything.')

    def handle(self, *args, **options):
        name = options['name']
        dry_run = options['dry_run']
        path = PACKS_DIR / f'{name}.json'
        if not path.exists():
            raise CommandError(f'No seed pack found at {path}')

        data = json.loads(path.read_text(encoding='utf-8'))
        version = data.get('version', '0.0.0')

        handler = getattr(self, f'_apply_{name}', None)
        if handler is None:
            raise CommandError(f'No loader implemented for pack "{name}" — add a _apply_{name} method.')

        self.stdout.write(f'Loading seed pack "{name}" v{version} (dry_run={dry_run})')
        self.created = 0
        self.updated = 0
        self.skipped_admin_edited = 0
        self.unchanged = 0

        with transaction.atomic():
            handler(name, version, data, dry_run=dry_run)
            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f'Done. Created={self.created} Updated={self.updated} '
            f'Unchanged={self.unchanged} SkippedAdminEdited={self.skipped_admin_edited}'
        ))

    # ─── Generic idempotent apply helper, reusable by any pack ─────────────

    def _apply_row(self, *, model, natural_key: dict, defaults: dict, pack: str, version: str):
        """Create-or-update `model` matched by `natural_key`, tracked via
        SeedRecord so a later admin edit is never clobbered by a re-run."""
        obj = model.objects.filter(**natural_key).first()
        checksum = _checksum(defaults)

        if obj is None:
            obj = model.objects.create(**natural_key, **defaults)
            SeedRecord.objects.update_or_create(
                pack=pack, content_type=ContentType.objects.get_for_model(model), object_id=str(obj.pk),
                defaults={'version': version, 'checksum': checksum},
            )
            self.created += 1
            return obj

        record = SeedRecord.objects.filter(
            pack=pack, content_type=ContentType.objects.get_for_model(model), object_id=str(obj.pk),
        ).first()
        current_checksum = _checksum({f: getattr(obj, f) for f in defaults})

        if record is not None and record.checksum != current_checksum:
            # The live row no longer matches what this pack last wrote —
            # an admin changed it since. Leave it alone.
            self.skipped_admin_edited += 1
            return obj

        if current_checksum == checksum:
            self.unchanged += 1
            SeedRecord.objects.update_or_create(
                pack=pack, content_type=ContentType.objects.get_for_model(model), object_id=str(obj.pk),
                defaults={'version': version, 'checksum': checksum},
            )
            return obj

        for field, value in defaults.items():
            setattr(obj, field, value)
        obj.save(update_fields=list(defaults.keys()))
        SeedRecord.objects.update_or_create(
            pack=pack, content_type=ContentType.objects.get_for_model(model), object_id=str(obj.pk),
            defaults={'version': version, 'checksum': checksum},
        )
        self.updated += 1
        return obj

    # ─── Pack-specific handlers ─────────────────────────────────────────────

    def _apply_core_geo(self, pack, version, data, *, dry_run):
        currency_by_code = {}
        for row in data['currencies']:
            obj = self._apply_row(
                model=Currency, natural_key={'code': row['code']},
                defaults={'name': row['name'], 'symbol': row.get('symbol', ''), 'minor_units': row.get('minor_units', 2)},
                pack=pack, version=version,
            )
            currency_by_code[row['code']] = obj

        tz_by_name = {}
        for row in data['timezones']:
            obj = self._apply_row(
                model=Timezone, natural_key={'name': row['name']}, defaults={},
                pack=pack, version=version,
            )
            tz_by_name[row['name']] = obj

        for row in data['countries']:
            defaults = {
                'iso3': row['iso3'], 'numeric_code': row.get('numeric_code', ''),
                'name': row['name'], 'phone_code': row.get('phone_code', ''),
                'date_format': row.get('date_format', 'DD/MM/YYYY'),
                'default_currency': currency_by_code.get(row.get('default_currency')),
                'default_timezone': tz_by_name.get(row.get('default_timezone')),
            }
            self._apply_row(
                model=Country, natural_key={'iso2': row['iso2']}, defaults=defaults,
                pack=pack, version=version,
            )

    def _apply_lookups_pack(self, pack, version, data):
        """Shared by core_lookups and india_core — both are {lookup_types, lookup_values} shaped."""
        for lt in data['lookup_types']:
            self._apply_row(
                model=LookupType, natural_key={'code': lt['code']},
                defaults={
                    'name': lt['name'], 'description': lt.get('description', ''),
                    'module': lt.get('module', ''), 'is_system': lt.get('is_system', False),
                    'allow_custom_values': lt.get('allow_custom_values', True),
                    'is_hierarchical': lt.get('is_hierarchical', False),
                    'attribute_schema': lt.get('attribute_schema', {}),
                },
                pack=pack, version=version,
            )

        for type_code, values in data.get('lookup_values', {}).items():
            lookup_type = LookupType.objects.get(code=type_code)
            for v in values:
                country = None
                if v.get('country'):
                    country = Country.objects.filter(iso2=v['country']).first()
                self._apply_row(
                    model=LookupValue, natural_key={'lookup_type': lookup_type, 'code': v['code']},
                    defaults={
                        'label': v['label'], 'description': v.get('description', ''),
                        'sort_order': v.get('sort_order', 0), 'attributes': v.get('attributes', {}),
                        'is_default': v.get('is_default', False), 'country': country,
                        'is_system': lookup_type.is_system,
                    },
                    pack=pack, version=version,
                )

    def _apply_core_lookups(self, pack, version, data, *, dry_run):
        self._apply_lookups_pack(pack, version, data)

    def _apply_india_core(self, pack, version, data, *, dry_run):
        self._apply_lookups_pack(pack, version, data)
