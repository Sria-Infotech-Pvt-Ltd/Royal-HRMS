"""
Creates the one primary LegalEntity (the company every existing employee, branch and org unit will belong to) from the existing
Company record. This is the first step of the company-separation work.

It is a command, not a migration, on purpose: a LegalEntity needs a country, currency and timezone, which come from the geo
seed pack (`load_seed_pack core_geo`). A migration that needed them would stop `migrate` on any environment that lacks them.

Safe by default:
  - DRY RUN unless --apply is given: it only prints what it would do;
  - idempotent: if a primary LegalEntity already exists it changes nothing;
  - never guesses: a missing Company, country, currency or timezone is an error that says what to run;
  - never touches employees, branches, positions or placements (that is the separate backfill step).
"""
from __future__ import annotations

import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import AuditLog, Company
from apps.platform_core.models import Country, LegalEntity

logger = logging.getLogger(__name__)

JURISDICTION_TO_COUNTRY = {Company.JURISDICTION_INDIA: 'IN'}
SEED_HINT = 'Run `python manage.py load_seed_pack core_geo` first, then try again.'


def _country_for(company: Company, iso2: str | None) -> Country:
    code = iso2 or JURISDICTION_TO_COUNTRY.get(company.jurisdiction)
    if not code:
        raise CommandError('The company is not in India, so pass --country <ISO2>. Nothing was changed.')
    country = Country.objects.filter(iso2=code.upper()).select_related('default_currency', 'default_timezone').first()
    if country is None:
        raise CommandError(f'Country {code.upper()} does not exist. {SEED_HINT}')
    if country.default_currency_id is None or country.default_timezone_id is None:
        raise CommandError(f'Country {country.iso2} has no default currency or timezone. {SEED_HINT}')
    return country


class Command(BaseCommand):
    help = 'Create the primary LegalEntity from the Company record (dry run unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Actually create it. Without this flag nothing is written.')
        parser.add_argument('--code', default='PRIMARY', help='Short unique code for the legal entity (default PRIMARY).')
        parser.add_argument('--country', default=None, help='ISO2 country code. Defaults from the Company jurisdiction (India = IN).')

    def handle(self, *args, **options):
        existing = LegalEntity.objects.filter(is_primary=True).first()
        if existing is not None:
            self.stdout.write(f'A primary legal entity already exists ({existing.code}). Nothing to do.')
            return
        company = Company.objects.first()
        if company is None:
            raise CommandError('There is no Company record to create the legal entity from. Nothing was changed.')
        country = _country_for(company, options['country'])
        plan = (f'code={options["code"]} legal_name={company.company_name!r} country={country.iso2} '
                f'currency={country.default_currency.code} timezone={country.default_timezone.name}')
        if not options['apply']:
            self.stdout.write(f'DRY RUN: would create a primary legal entity: {plan}\nRe-run with --apply to create it.')
            return
        with transaction.atomic():
            entity = LegalEntity.objects.create(
                code=options['code'], legal_name=company.company_name, country=country, base_currency=country.default_currency,
                timezone=country.default_timezone, jurisdiction=company.jurisdiction, is_primary=True, is_active=True,
            )
            AuditLog.objects.create(user=None, action='create', module='legal_entity', object_id=str(entity.pk),
                                    changes={'code': entity.code, 'source': 'ensure_primary_legal_entity'})
        logger.info('Primary legal entity %s created from the Company record', entity.code)
        self.stdout.write(self.style.SUCCESS(f'Created the primary legal entity: {plan}'))
