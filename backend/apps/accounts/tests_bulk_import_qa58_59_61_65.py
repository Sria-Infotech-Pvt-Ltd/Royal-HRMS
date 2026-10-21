"""
Regression tests for the QA pass covering:

#58 (Medium) — the "failed" count in a bulk-import result used to be
len(row_errors) (one entry per FIELD-level error), so a single row with
several invalid fields inflated the reported failed-row count far beyond
the number of rows that actually failed. It must now count distinct rows,
and created + skipped + failed must always equal total_rows.

#59 (Medium) — assign_position()'s designation/department sync used to look
up the "current" placement as of TODAY, so a bulk-imported (or hired)
employee with a future Date of Joining got a real Placement row created but
no Designation synced onto User.designation at all — the Employee Directory
table showed a blank "—" Position/Designation even though the Placement
existed.

#61 (Medium) — a future date_of_birth (e.g. 2030-01-01) was accepted with no
validation at all during bulk import.

#65 (Low) — an org unit that doesn't exist at all used to report its error
against the "position" field ("No active position X in org unit
NoSuchUnit"), misleading the user into thinking the position name was
wrong when it was really the org unit name. It must report against
'org_unit' instead whenever the org unit itself has no positions at all.

Style follows apps/accounts/tests_bulk_import_sample.py /
tests_hire_wizard.py: make_role/make_user factories, APIClient, reverse().
"""
from __future__ import annotations

import io

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import OrgUnit, Position, Role
from apps.branch.models import Branch, City, State


def _csv_bytes(rows: list[str]) -> bytes:
    header = (
        'First Name,Last Name,Work Email,Role,Org Unit,Position,'
        'Company Code,Date of Joining,Date of Birth\n'
    )
    return (header + '\n'.join(rows)).encode('utf-8')


class BulkImportQaRegressionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.hr_role = make_role('hr_admin_qa_test', permission_codenames=['employees.create'])
        self.hr_user = make_user('hr-qa@test.com', role=self.hr_role, password='TestPass123!')
        self.client.force_authenticate(user=self.hr_user)

        state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
        city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
        self.branch = Branch.objects.create(
            branch_code='BR01', branch_name='Test Branch', state=state, city=city,
        )
        self.unit = OrgUnit.objects.create(name='Engineering')
        self.position = Position.objects.create(org_unit=self.unit, title='Software Engineer', grade='L2')
        self.employee_role = make_role('employee_qa_test', permission_codenames=[])

    def _import(self, rows):
        upload = SimpleUploadedFile('import.csv', _csv_bytes(rows), content_type='text/csv')
        return self.client.post(
            reverse('employee-bulk-import'), {'file': upload}, format='multipart',
        )

    def test_failed_count_is_distinct_rows_not_field_errors(self):
        """One row with 4 invalid fields (bad email, unknown role, unknown
        org unit, garbage DOB) must count as 1 failed row, not 4 — and
        created + skipped + failed must equal total_rows."""
        rows = [
            # Row 2: valid — created.
            f'John,Doe,john.doe@test.com,{self.employee_role.display_name},'
            f'Engineering,Software Engineer,BR01,2024-01-01,1994-01-01',
            # Row 3: multiple field errors in ONE row (bad email format,
            # unknown role, unknown org unit, invalid DOB format).
            'Jane,Bad,not-an-email,NoSuchRole,NoSuchUnit,NoSuchPosition,'
            'BR01,not-a-date,not-a-date',
        ]
        resp = self._import(rows)
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data['data']
        self.assertEqual(data['created'], 1)
        self.assertEqual(data['skipped'], 0)
        self.assertEqual(data['failed'], 1, data['errors'])
        self.assertEqual(data['created'] + data['skipped'] + data['failed'], data['total_rows'])
        # All the individual field errors for the bad row are still surfaced.
        self.assertGreater(len(data['errors']), 1)
        self.assertTrue(all(e['row'] == 3 for e in data['errors']))

    def test_error_identifier_shown_even_when_serializer_itself_fails(self):
        """QA #62 companion check: even a row that fails plain serializer
        validation (garbage email) surfaces the RAW email string as the
        error table's identifier, not a blank."""
        rows = [
            f'Jane,Bad,not-an-email,{self.employee_role.display_name},'
            f'Engineering,Software Engineer,BR01,2024-01-01,1994-01-01',
        ]
        resp = self._import(rows)
        self.assertEqual(resp.status_code, 200, resp.data)
        errors = resp.data['data']['errors']
        self.assertTrue(errors)
        self.assertEqual(errors[0]['identifier'], 'not-an-email')

    def test_future_date_of_birth_rejected(self):
        rows = [
            f'John,Future,john.future@test.com,{self.employee_role.display_name},'
            f'Engineering,Software Engineer,BR01,2024-01-01,2030-01-01',
        ]
        resp = self._import(rows)
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data['data']
        self.assertEqual(data['created'], 0)
        self.assertEqual(data['failed'], 1)
        self.assertTrue(any(e['field'] == 'date_of_birth' for e in data['errors']))

    def test_unknown_org_unit_reports_against_org_unit_field(self):
        rows = [
            f'John,Doe,john.orgunit@test.com,{self.employee_role.display_name},'
            f'NoSuchUnit,Software Engineer,BR01,2024-01-01,1994-01-01',
        ]
        resp = self._import(rows)
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data['data']
        self.assertEqual(data['created'], 0)
        errs = data['errors']
        self.assertTrue(errs)
        self.assertEqual(errs[0]['field'], 'org_unit')
        self.assertIn('Org unit', errs[0]['message'])
        self.assertIn('NoSuchUnit', errs[0]['message'])

    def test_unknown_position_in_real_org_unit_still_reports_against_position(self):
        rows = [
            f'John,Doe,john.position@test.com,{self.employee_role.display_name},'
            f'Engineering,NoSuchPosition,BR01,2024-01-01,1994-01-01',
        ]
        resp = self._import(rows)
        self.assertEqual(resp.status_code, 200, resp.data)
        errs = resp.data['data']['errors']
        self.assertTrue(errs)
        self.assertEqual(errs[0]['field'], 'position')

    def test_designation_synced_for_future_date_of_joining(self):
        """QA #59 — a bulk-imported employee whose Date of Joining is in the
        future must still get User.designation synced from the Position
        assign_position() just placed them into, not left blank."""
        from apps.accounts.models import User
        rows = [
            f'Future,Hire,future.hire@test.com,{self.employee_role.display_name},'
            f'Engineering,Software Engineer,BR01,2099-01-01,1994-01-01',
        ]
        resp = self._import(rows)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['created'], 1)
        user = User.objects.get(email='future.hire@test.com')
        self.assertEqual(user.designation, 'Software Engineer')


class BulkImportRowAtomicityTests(TestCase):
    """AIRA-UAT-003 — a bulk import request that dies partway through used to
    leave whatever had been committed so far in place with no way to tell
    (no transaction around a row's multiple writes: User, Position
    assignment, EmployeeProfile, salary config, leave balances). Each row is
    now its own transaction.atomic() block, so a failure anywhere in a row
    rolls that whole row back -- confirms a half-created employee (User with
    no leave balances, e.g.) can no longer exist."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.hr_role = make_role('hr_admin_atomic_test', permission_codenames=['employees.create'])
        self.hr_user = make_user('hr-atomic@test.com', role=self.hr_role, password='TestPass123!')
        self.client.force_authenticate(user=self.hr_user)

        state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
        city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
        self.branch = Branch.objects.create(
            branch_code='BR02', branch_name='Atomicity Test Branch', state=state, city=city,
        )
        self.unit = OrgUnit.objects.create(name='Engineering Atomic')
        self.position = Position.objects.create(org_unit=self.unit, title='Software Engineer', grade='L2')
        # A second, distinct position so the two rows below don't collide on
        # the same seat/date range (a real overlap failure, caught earlier
        # than the step this test is actually targeting) -- each row needs
        # its OWN successful position assignment so the forced failure
        # further down the row (leave allocation) is what rolls it back.
        self.position_2 = Position.objects.create(org_unit=self.unit, title='Senior Engineer', grade='L3')
        self.employee_role = make_role('employee_atomic_test', permission_codenames=[])

    def _import(self, rows):
        upload = SimpleUploadedFile('import.csv', _csv_bytes(rows), content_type='text/csv')
        return self.client.post(
            reverse('employee-bulk-import'), {'file': upload}, format='multipart',
        )

    def test_failure_partway_through_a_row_leaves_no_partial_user(self):
        from unittest.mock import patch

        from apps.accounts.models import User

        rows = [
            # Row 2: valid, must still succeed independently of row 3 below.
            f'Good,Row,good.row@test.com,{self.employee_role.display_name},'
            f'Engineering Atomic,Software Engineer,BR02,2024-01-01,1994-01-01',
            # Row 3: a different position (no overlap with row 2), passes
            # every validation step, but its leave allocation (the LAST
            # write in the per-row block) is forced to blow up -- simulates
            # the request dying partway through this row's writes, after
            # the User/position assignment/profile have already happened.
            f'Partial,Row,partial.row@test.com,{self.employee_role.display_name},'
            f'Engineering Atomic,Senior Engineer,BR02,2024-01-01,1994-01-01',
        ]
        with patch(
            'apps.hrms.views.leave_shared._allocate_leaves_for_employee',
            side_effect=[None, Exception('simulated mid-row failure')],
        ):
            resp = self._import(rows)

        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data['data']
        self.assertEqual(data['created'], 1)
        self.assertEqual(data['failed'], 1, data['errors'])

        # The row that failed left NO trace at all -- not a half-created
        # User with no position/profile/leave balances.
        self.assertFalse(User.objects.filter(email='partial.row@test.com').exists())
        # The unrelated, fully-successful row was never touched by the other
        # row's rollback -- each row really is its own transaction.
        self.assertTrue(User.objects.filter(email='good.row@test.com').exists())


class BulkImportStatusTests(TestCase):
    """AIRA-UAT-003 — when the import response is lost the browser asks the server what happened to its batch."""

    def setUp(self):
        import uuid

        cache.clear()
        self.uuid = uuid
        self.client = APIClient()
        hr_role = make_role('hr_admin_status_test', permission_codenames=['employees.create'])
        self.hr_user = make_user('hr-status@test.com', role=hr_role, password='TestPass123!')
        self.client.force_authenticate(user=self.hr_user)
        state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
        city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
        Branch.objects.create(branch_code='BR03', branch_name='Status Test Branch', state=state, city=city)
        unit = OrgUnit.objects.create(name='Engineering Status')
        Position.objects.create(org_unit=unit, title='Software Engineer', grade='L2')
        self.employee_role = make_role('employee_status_test', permission_codenames=[])

    def _import(self, batch_id=None):
        row = (f'Stat,Tester,stat.tester@test.com,{self.employee_role.display_name},'
               f'Engineering Status,Software Engineer,BR03,2024-01-01,1994-01-01')
        data = {'file': SimpleUploadedFile('import.csv', _csv_bytes([row]), content_type='text/csv')}
        if batch_id:
            data['batch_id'] = batch_id
        return self.client.post(reverse('employee-bulk-import'), data, format='multipart')

    def _status(self, batch_id):
        return self.client.get(reverse('employee-bulk-import-status', args=[batch_id]))

    def test_unknown_batch_is_reported_as_not_received(self):
        resp = self._status(self.uuid.uuid4())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['state'], 'not_received')

    def _log(self, action, **changes):
        from apps.accounts.models import AuditLog

        return AuditLog.objects.create(user=self.hr_user, action=action, module='accounts', changes=changes)

    def test_completed_batch_reports_exact_counts(self):
        batch_id = str(self.uuid.uuid4())
        self._log('bulk_employee_import_started', batch_id=batch_id, total_rows=50)
        self._log('bulk_employee_import', batch_id=batch_id, total_rows=50, created=48, skipped=1, failed=1)
        data = self._status(batch_id).data['data']
        self.assertEqual(data['state'], 'completed')
        self.assertEqual((data['total_rows'], data['created'], data['skipped'], data['failed']), (50, 48, 1, 1))

    def test_started_but_never_finished_batch_is_interrupted_with_partial_count(self):
        from datetime import timedelta

        from django.utils import timezone

        from apps.accounts.models import AuditLog

        batch_id = str(self.uuid.uuid4())
        started = AuditLog.objects.create(
            user=self.hr_user, action='bulk_employee_import_started', module='accounts',
            changes={'batch_id': batch_id, 'total_rows': 50},
        )
        AuditLog.objects.filter(pk=started.pk).update(created_at=timezone.now() - timedelta(minutes=30))
        data = self._status(batch_id).data['data']
        self.assertEqual(data['state'], 'interrupted')
        self.assertEqual(data['total_rows'], 50)
        self.assertIn('created_since_start', data)

    def test_recently_started_batch_is_in_progress(self):
        from apps.accounts.models import AuditLog

        batch_id = str(self.uuid.uuid4())
        AuditLog.objects.create(
            user=self.hr_user, action='bulk_employee_import_started', module='accounts',
            changes={'batch_id': batch_id, 'total_rows': 50},
        )
        self.assertEqual(self._status(batch_id).data['data']['state'], 'in_progress')

    def test_upload_records_the_client_batch_id_and_replaces_an_invalid_one(self):
        from apps.accounts.models import AuditLog

        good = str(self.uuid.uuid4())
        self._import(good)
        self.assertTrue(AuditLog.objects.filter(action='bulk_employee_import_started', changes__batch_id=good).exists())
        self._import('not-a-uuid')
        recorded = [log.changes['batch_id'] for log in AuditLog.objects.filter(action='bulk_employee_import_started')]
        self.assertEqual(len(recorded), 2)
        for value in recorded:
            self.assertEqual(str(self.uuid.UUID(value)), value)  # every stored id is a real UUID

    def test_other_users_batch_is_not_visible(self):
        batch_id = str(self.uuid.uuid4())
        self._log('bulk_employee_import_started', batch_id=batch_id, total_rows=5)
        other_role = make_role('hr_admin_status_other', permission_codenames=['employees.create'])
        self.client.force_authenticate(user=make_user('hr-other@test.com', role=other_role, password='TestPass123!'))
        self.assertEqual(self._status(batch_id).data['data']['state'], 'not_received')

    def test_user_without_import_permission_is_forbidden(self):
        self.client.force_authenticate(user=make_user('plain-status@test.com', role=self.employee_role, password='TestPass123!'))
        self.assertEqual(self._status(self.uuid.uuid4()).status_code, 403)
