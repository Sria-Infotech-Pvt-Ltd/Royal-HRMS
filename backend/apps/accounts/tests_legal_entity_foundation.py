"""
Company-separation step 1-2: the nullable company key on the six core tables, the employee-ID prefix, and the command that
creates the primary LegalEntity.

These tests prove the change is invisible to existing behaviour (every key is optional, nothing is filled in yet) and that the
command is dry-run by default, idempotent, refuses to guess, and never touches existing rows.
"""
from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import ProtectedError
from django.test import TestCase

from apps.accounts.factories import make_user
from apps.accounts.models import AuditLog, Company, EmployeeCodeSeries, JobTemplate, OrgUnit, User
from apps.accounts.models_org_masters import Designation
from apps.accounts.tests_employee_scope import make_branch
from apps.branch.models import Branch
from apps.platform_core.models import Country, Currency, LegalEntity, Timezone

KEYED_MODELS = (User, Branch, OrgUnit, Designation, JobTemplate, EmployeeCodeSeries)


def _run(*args) -> str:
    out = StringIO()
    call_command('ensure_primary_legal_entity', *args, stdout=out)
    return out.getvalue()


def _geo():
    inr = Currency.objects.create(code='INR', name='Indian Rupee')
    tz = Timezone.objects.create(name='Asia/Kolkata')
    return Country.objects.create(iso2='IN', iso3='IND', name='India', default_currency=inr, default_timezone=tz)


class CompanyKeyFieldTests(TestCase):
    def test_every_core_model_has_an_optional_company_key_with_no_index_yet(self):
        for model in KEYED_MODELS:
            field = model._meta.get_field('legal_entity')
            self.assertTrue(field.null and field.blank, model.__name__)
            self.assertFalse(field.db_index, model.__name__)               # the index comes later, created concurrently

    def test_existing_ways_of_creating_records_still_work_without_a_company(self):
        user = make_user('foundation@test.com', employee_id='FD001')
        branch = make_branch('FD-A', 'Foundation Branch')
        unit = OrgUnit.objects.create(name='Foundation Unit')
        template = JobTemplate.objects.create(name='Foundation Template')
        for record in (user, branch, unit, template):
            self.assertIsNone(record.legal_entity_id)

    def test_a_company_cannot_be_deleted_while_records_belong_to_it(self):
        country = _geo()
        entity = LegalEntity.objects.create(code='T1', legal_name='T', country=country, base_currency=country.default_currency, timezone=country.default_timezone)
        unit = OrgUnit.objects.create(name='Protected Unit', legal_entity=entity)
        with self.assertRaises(ProtectedError):
            entity.delete()
        unit.delete()
        entity.delete()

    def test_employee_id_prefix_defaults_to_blank_so_existing_ids_never_change(self):
        country = _geo()
        entity = LegalEntity.objects.create(code='T2', legal_name='T', country=country, base_currency=country.default_currency, timezone=country.default_timezone)
        self.assertEqual(entity.employee_id_prefix, '')


class EnsurePrimaryLegalEntityTests(TestCase):
    def setUp(self):
        Company.objects.create(company_name='Test Company Pvt Ltd')

    def test_dry_run_by_default_writes_nothing(self):
        _geo()
        self.assertIn('DRY RUN', _run())
        self.assertFalse(LegalEntity.objects.exists())

    def test_apply_creates_exactly_one_primary_entity_and_an_audit_entry(self):
        _geo()
        _run('--apply')
        entity = LegalEntity.objects.get()
        self.assertEqual((entity.is_primary, entity.legal_name, entity.employee_id_prefix), (True, 'Test Company Pvt Ltd', ''))
        self.assertEqual(AuditLog.objects.filter(action='create', module='legal_entity').count(), 1)

    def test_running_it_again_changes_nothing(self):
        _geo()
        _run('--apply')
        self.assertIn('already exists', _run('--apply'))
        self.assertEqual(LegalEntity.objects.count(), 1)

    def test_it_never_touches_existing_employees_branches_or_org_units(self):
        _geo()
        user, branch, unit = make_user('keep@test.com', employee_id='FD002'), make_branch('FD-B', 'Keep Branch'), OrgUnit.objects.create(name='Keep Unit')
        _run('--apply')
        for record in (user, branch, unit):
            record.refresh_from_db()
            self.assertIsNone(record.legal_entity_id)                                    # filling these in is a separate, approved step

    def test_missing_geo_masters_is_an_error_that_says_what_to_run(self):
        with self.assertRaisesMessage(CommandError, 'load_seed_pack core_geo'):
            _run('--apply')
        self.assertFalse(LegalEntity.objects.exists())

    def test_a_country_without_currency_or_timezone_is_refused_not_guessed(self):
        Country.objects.create(iso2='IN', iso3='IND', name='India')
        with self.assertRaisesMessage(CommandError, 'no default currency or timezone'):
            _run('--apply')
        self.assertFalse(LegalEntity.objects.exists())

    def test_no_company_record_is_an_error(self):
        Company.objects.all().delete()
        _geo()
        with self.assertRaisesMessage(CommandError, 'no Company record'):
            _run('--apply')
