"""UAT-035: org-unit report (read-only), safe merge utility (dry run by default, audited), and the optional hire-without-vacancy flag."""
import datetime
import json
import tempfile
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, OrgUnit, Placement, Position
from apps.accounts.services_org_units import (
    OrgUnitMergeError, build_org_unit_report, merge_org_units, names_look_alike,
)

TODAY = datetime.date.today()


def _seat(unit, title, holder=None, is_chief=False):
    position = Position.objects.create(org_unit=unit, title=title, is_chief=is_chief)
    if holder:
        Placement.objects.create(position=position, employee=holder, effective_from=TODAY - datetime.timedelta(days=5))
    return position


class OrgUnitReportTests(TestCase):
    def setUp(self):
        self.development = OrgUnit.objects.create(name='Zeta Development')
        self.app_dev = OrgUnit.objects.create(name='Zeta Application Development')
        self.hr = OrgUnit.objects.create(name='Quokka Finance')
        _seat(self.development, 'Developer', make_user('dev1@test.com', employee_id='EMPOU01'))
        _seat(self.development, 'Developer 2')            # vacant
        _seat(self.app_dev, 'Engineer', make_user('dev2@test.com', employee_id='EMPOU02'))

    def test_counts_per_unit(self):
        rows = {row['name']: row for row in build_org_unit_report()}
        self.assertEqual(
            (rows['Zeta Development']['employee_count'], rows['Zeta Development']['position_count'], rows['Zeta Development']['vacancy_count']),
            (1, 2, 1),
        )
        self.assertEqual(rows['Quokka Finance']['position_count'], 0)

    def test_probable_duplicates_by_name(self):
        rows = {row['name']: row for row in build_org_unit_report()}
        self.assertIn('Zeta Application Development', rows['Zeta Development']['probable_duplicates'])
        self.assertEqual(rows['Quokka Finance']['probable_duplicates'], [])
        self.assertTrue(names_look_alike('Testing/QA', 'Testing QA'))
        self.assertFalse(names_look_alike('Finance', 'Facilities'))

    def test_report_command_is_read_only(self):
        before = OrgUnit.objects.count()
        out = StringIO()
        call_command('org_unit_report', stdout=out)
        self.assertIn('Nothing was changed', out.getvalue())
        self.assertEqual(OrgUnit.objects.count(), before)


class OrgUnitMergeTests(TestCase):
    def setUp(self):
        self.source = OrgUnit.objects.create(name='Zeta Application Development')
        self.target = OrgUnit.objects.create(name='Zeta Development')
        self.child = OrgUnit.objects.create(name='Mobile', parent=self.source)
        self.holder = make_user('merge1@test.com', employee_id='EMPMG01')
        self.seat = _seat(self.source, 'Engineer', self.holder)
        self.vacant = _seat(self.source, 'Engineer 2')

    def test_dry_run_reports_but_changes_nothing(self):
        steps = merge_org_units([(str(self.source.pk), str(self.target.pk))], dry_run=True)
        self.assertEqual((steps[0].positions_moved, steps[0].employees_moved, steps[0].children_reparented), (2, 1, 1))
        self.seat.refresh_from_db()
        self.source.refresh_from_db()
        self.assertEqual(self.seat.org_unit_id, self.source.pk)
        self.assertTrue(self.source.is_active)
        self.assertFalse(AuditLog.objects.filter(action='org_unit_merged').exists())

    def test_real_merge_moves_positions_employees_and_children_and_audits(self):
        actor = make_user('merge-actor@test.com', employee_id='EMPMG99')
        merge_org_units([('Zeta Application Development', 'Zeta Development')], actor=actor, dry_run=False)
        self.seat.refresh_from_db()
        self.vacant.refresh_from_db()
        self.child.refresh_from_db()
        self.source.refresh_from_db()
        self.assertEqual((self.seat.org_unit_id, self.vacant.org_unit_id), (self.target.pk, self.target.pk))
        self.assertEqual(self.child.parent_id, self.target.pk)
        self.assertFalse(self.source.is_active)  # deactivated, never deleted
        # the employee's seat (and so their unit) is the target now, and the placement history is intact
        self.assertTrue(Placement.objects.filter(employee=self.holder, position=self.seat).exists())
        entry = AuditLog.objects.get(action='org_unit_merged')
        self.assertEqual(entry.changes['positions_moved'], 2)
        self.assertEqual(entry.user_id, actor.id)

    def test_target_keeps_its_chief_when_both_have_one(self):
        _seat(self.target, 'Head of Development', is_chief=True)
        moving_chief = _seat(self.source, 'Head of App Dev', is_chief=True)
        steps = merge_org_units([(str(self.source.pk), str(self.target.pk))], dry_run=False)
        moving_chief.refresh_from_db()
        self.assertEqual(steps[0].chief_demoted, 'Head of App Dev')
        self.assertFalse(moving_chief.is_chief)
        self.assertEqual(Position.objects.filter(org_unit=self.target, is_chief=True).count(), 1)

    def test_unsafe_mappings_are_refused_before_anything_changes(self):
        other = OrgUnit.objects.create(name='Other')
        bad_pairs = [
            [(str(self.source.pk), str(self.source.pk))],                                  # into itself
            [(str(self.source.pk), str(self.child.pk))],                                   # into its own child
            [(str(self.source.pk), str(self.target.pk)), (str(self.target.pk), str(other.pk))],  # chain
            [(str(self.source.pk), 'No Such Unit')],
        ]
        for pairs in bad_pairs:
            with self.assertRaises(OrgUnitMergeError):
                merge_org_units(pairs, dry_run=False)
        self.seat.refresh_from_db()
        self.assertEqual(self.seat.org_unit_id, self.source.pk)

    def test_command_is_dry_run_unless_apply(self):
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as handle:
            json.dump([{'source': 'Zeta Application Development', 'target': 'Zeta Development'}], handle)
        out = StringIO()
        call_command('merge_org_units', mapping=handle.name, stdout=out)
        self.assertIn('DRY RUN', out.getvalue())
        self.seat.refresh_from_db()
        self.assertEqual(self.seat.org_unit_id, self.source.pk)
        call_command('merge_org_units', mapping=handle.name, apply=True, stdout=StringIO())
        self.seat.refresh_from_db()
        self.assertEqual(self.seat.org_unit_id, self.target.pk)
        with self.assertRaises(CommandError):
            call_command('merge_org_units', mapping='/no/such/file.json', stdout=StringIO())


class HireWithoutVacancyTests(TestCase):
    """The vacancy requirement stays: a hire names an existing position (the hire dialog offers a "create one" shortcut first)."""

    def setUp(self):
        role = make_role('hr_novacancy_test', permission_codenames=['employees.create'])
        self.hr_user = make_user('hr-novacancy@test.com', role=role)
        self.unit = OrgUnit.objects.create(name='Operations')  # no positions at all
        self.client = APIClient()
        self.client.force_authenticate(user=self.hr_user)

    def test_a_hire_without_a_position_is_refused_and_creates_no_seat(self):
        body = {
            'reason': 'new_position', 'effective_from': (TODAY + datetime.timedelta(days=3)).isoformat(),
            'org_unit': str(self.unit.pk), 'position_title': 'Operations Executive',  # extra fields are ignored, never auto-create
        }
        response = self.client.post(reverse('hire-action-list'), body, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['message'], 'Select a position.')
        self.assertFalse(Position.objects.filter(org_unit=self.unit).exists())
        self.assertFalse(AuditLog.objects.filter(action='position_auto_created').exists())

    def test_there_is_no_auto_create_setting(self):
        from django.conf import settings
        self.assertFalse(hasattr(settings, 'HIRE_AUTO_CREATE_POSITION'))
