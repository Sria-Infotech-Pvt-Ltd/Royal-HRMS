"""
seed_company_structure: the company, branches and service/department structure are created through the app's own serializers,
are verified through the existing list APIs, reuse matching units that already exist, and are idempotent.
"""
from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_user
from apps.accounts.models import AuditLog, Company, OrgUnit
from apps.branch.models import Branch, City, State


def _run(*args) -> str:
    out = StringIO()
    call_command('seed_company_structure', *args, stdout=out)
    return out.getvalue()


def _unit(name: str, parent=None) -> OrgUnit:
    unit, _ = OrgUnit.objects.get_or_create(name=name, parent=parent)
    return unit


class SeedCompanyStructureTests(TestCase):
    def setUp(self):
        state, _ = State.objects.get_or_create(name='Telangana', defaults={'code': 'TG'})
        City.objects.get_or_create(name='Hyderabad', state=state)
        self.software = _unit('Software Services', _unit('SRIA'))  # the org chart the data migration already provides
        for name in ('SAP', 'AI & ML', 'Testing / QA'):  # units the real org chart already has, so a run creates a known five
            _unit(name, self.software)

    def _under_software(self, name: str) -> OrgUnit:
        return OrgUnit.objects.get(name=name, parent=self.software)

    def test_creates_the_company_two_branches_and_the_department_structure_with_the_right_relationships(self):
        _run()
        self.assertEqual(list(Company.objects.values_list('company_name', flat=True)), ['Sri Infotech'])

        branches = {b.branch_name: b for b in Branch.objects.select_related('state', 'city')}
        self.assertEqual(set(branches), {'Kondapur', 'Mulugu'})
        self.assertEqual((branches['Kondapur'].state.name, branches['Kondapur'].city.name), ('Telangana', 'Hyderabad'))
        self.assertEqual((branches['Mulugu'].state.name, branches['Mulugu'].city.name), ('Telangana', 'Mulugu'))  # city created the way the Branch screen does
        self.assertNotEqual(branches['Kondapur'].branch_code, branches['Mulugu'].branch_code)

        web = self._under_software('Web Development')
        self.assertEqual(sorted(web.children.values_list('name', flat=True)), ['Backend Development', 'Frontend Development'])
        for name in ('Data Analytics', 'Deployment'):
            self.assertEqual(self._under_software(name).children.count(), 0)
        for unit in (web, *web.children.all(), self._under_software('Data Analytics'), self._under_software('Deployment')):
            self.assertTrue(unit.is_department_level, unit.name)

    def test_existing_matching_units_are_reused_not_duplicated_or_renamed(self):
        sap, ai_ml, testing = (self._under_software(n) for n in ('SAP', 'AI & ML', 'Testing / QA'))
        before = OrgUnit.objects.count()
        _run()
        self.assertFalse(OrgUnit.objects.filter(name__in=['AI / ML', 'Software Testing / QA']).exists())
        for unit in (sap, ai_ml, testing):
            unit.refresh_from_db()
            self.assertTrue(unit.is_department_level)  # only the department marker changed
        self.assertEqual((sap.name, ai_ml.name, testing.name), ('SAP', 'AI & ML', 'Testing / QA'))
        # new: Web Development, Frontend Development, Backend Development, Data Analytics, Deployment
        self.assertEqual(OrgUnit.objects.count() - before, 5)

    def test_running_it_again_creates_nothing_new(self):
        _run()
        counts = (Company.objects.count(), Branch.objects.count(), OrgUnit.objects.count(), City.objects.count())
        second = _run()
        self.assertEqual((Company.objects.count(), Branch.objects.count(), OrgUnit.objects.count(), City.objects.count()), counts)
        self.assertIn('Created 0;', second)

    def test_dry_run_writes_nothing(self):
        counts = (Company.objects.count(), Branch.objects.count(), OrgUnit.objects.count(), City.objects.count())
        output = _run('--dry-run')
        self.assertIn('DRY RUN', output)
        self.assertIn('Web Development / Frontend Development', output)
        self.assertEqual((Company.objects.count(), Branch.objects.count(), OrgUnit.objects.count(), City.objects.count()), counts)

    def test_a_different_existing_company_is_left_unchanged_and_reported(self):
        Company.objects.create(company_name='Another Company', address='Elsewhere', city='Pune')
        output = _run()
        self.assertEqual(list(Company.objects.values_list('company_name', flat=True)), ['Another Company'])
        self.assertIn('A different company already exists', output)

    def test_no_audit_rows_are_written_without_an_actor(self):
        _run()
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_audit_rows_name_the_actor_like_the_screens_do(self):
        actor = make_user('seed.actor@test.com', is_superuser=True)
        _run('--actor-email', actor.email)
        self.assertEqual(AuditLog.objects.filter(user=actor, module='company').count(), 1)
        self.assertEqual(AuditLog.objects.filter(user=actor, module='branch').count(), 2)
        self.assertEqual(AuditLog.objects.filter(user=actor, module='org_structure').count(), 5)  # only the units actually created

    def test_an_unknown_actor_is_refused(self):
        with self.assertRaises(CommandError):
            _run('--actor-email', 'nobody@test.com')

    def test_the_saved_records_show_up_through_the_existing_apis(self):
        _run()
        client = APIClient()
        client.force_authenticate(user=make_user('seed.admin@test.com', is_superuser=True))

        company = client.get(reverse('company')).json()['data']
        self.assertEqual(company['company_name'], 'Sri Infotech')

        branches = client.get(reverse('branch-list-create')).json()['data']
        names = sorted(b['branch_name'] for b in (branches['results'] if isinstance(branches, dict) else branches))
        self.assertEqual(names, ['Kondapur', 'Mulugu'])

        units = client.get(reverse('org-unit-list') + '?page_size=500').json()['data']
        rows = units['results'] if isinstance(units, dict) else units
        by_name = {u['name']: u for u in rows if u['name'] in {'Web Development', 'Frontend Development', 'Backend Development'}}
        self.assertEqual(by_name['Frontend Development']['parent'], by_name['Web Development']['id'])
        self.assertEqual(by_name['Backend Development']['parent'], by_name['Web Development']['id'])
        self.assertEqual(by_name['Web Development']['parent'], str(self.software.pk))
