"""
Bulk employee import from Excel: template, read-only preview, error report, all-or-nothing commit.

Covers: permission, branch restriction that survives a doctored spreadsheet, preview writes nothing, hash/batch checks,
duplicates are reported (never skipped), one transaction, invites after commit with failures reported separately, and no
personal data in the error report.
"""
from __future__ import annotations

import io
import uuid
from unittest import mock

import openpyxl
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, EmployeeProfile, OrgUnit, Permission, Placement, Position, PositionPermission, User
from apps.accounts.services_employee_import import COLUMNS, file_sha256
from apps.accounts.services_employee_import_commit import ImportRejected, commit_import
from apps.accounts.tests_employee_scope import make_branch

PREVIEW, COMMIT, ERRORS, TEMPLATE = (
    '/api/employees/bulk-import/preview/', '/api/employees/bulk-import/commit/',
    '/api/employees/bulk-import/errors/', '/api/employees/bulk-import/template/',
)
HR_KEYS = ['employees.view', 'employees.create', 'employees.edit']
HEADERS = [column.header for column in COLUMNS]
INVITE = 'apps.accounts.services_employee_import_invites.send_activation_invite'


def _workbook(rows: list[dict], headers: list[str] | None = None) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = 'Employees'
    keys = {column.header: column.key for column in COLUMNS}
    headers = headers or HEADERS
    sheet.append(headers)
    for row in rows:
        sheet.append([row.get(keys[header], '') for header in headers])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _upload(content: bytes, name: str = 'import.xlsx') -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


class _ImportCase(TestCase):
    def setUp(self):
        cache.clear()
        self.hyd = make_branch('IMP-HYD', 'Import Hyderabad')
        self.blr = make_branch('IMP-BLR', 'Import Bengaluru')
        self.unit = OrgUnit.objects.create(name='Import Unit')
        # A seat holds one person at a time, so every imported row needs its own vacant seat.
        self.seats = {n: self._seat(f'Analyst {n}', ['leave.view']) for n in range(1, 8)}
        self.analyst = self.seats[1]
        self.lead = self._seat('Team Lead', ['leave.view'], can_manage_team=True)
        self.root_seat = self._seat('Super Seat', ['settings.edit'])
        self.hr = make_user('imp_hr@test.com', role=make_role('imp_hr', permission_codenames=HR_KEYS), employee_id='IH001', branch=self.hyd.branch_name)
        self.admin = make_user('imp_admin@test.com', employee_id='IA001', is_superuser=True, branch=self.hyd.branch_name)
        self.plain = make_user('imp_plain@test.com', employee_id='IP001', branch=self.hyd.branch_name)
        self.hyd_manager = make_user(
            'imp_mgr_hyd@test.com', role=make_role('imp_mgr_h', permission_codenames=['leave.approve'], can_manage_team=True),
            employee_id='IM001', branch=self.hyd.branch_name,
        )
        self.blr_manager = make_user(
            'imp_mgr_blr@test.com', role=make_role('imp_mgr_b', permission_codenames=['leave.approve'], can_manage_team=True),
            employee_id='IM002', branch=self.blr.branch_name,
        )

    def _seat(self, title, keys, **flags) -> Position:
        seat = Position.objects.create(org_unit=self.unit, title=title, grade='L3', **flags)
        for key in keys:
            PositionPermission.objects.create(position=seat, permission=Permission.objects.get_or_create(
                codename=key, defaults={'module': key.partition('.')[0], 'action': key.partition('.')[2]})[0])
        return seat

    def row(self, n: int = 1, **overrides) -> dict:
        row = {
            'first_name': f'Asha{n}', 'last_name': 'Verma', 'email': f'asha{n}@import.test', 'date_of_joining': '2026-11-10',
            'branch': 'IMP-HYD', 'org_unit': 'Import Unit', 'position': f'Analyst {n}',
        }
        row.update(overrides)
        return row

    def client_for(self, user) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def preview(self, user, rows, **kw):
        return self.client_for(user).post(PREVIEW, {'file': _upload(_workbook(rows, **kw))}, format='multipart')

    def commit(self, user, rows, batch=None, content=None, file_hash=None):
        content = content if content is not None else _workbook(rows)
        return self.client_for(user).post(COMMIT, {
            'file': _upload(content), 'batch_id': batch or str(uuid.uuid4()), 'file_hash': file_hash or file_sha256(content),
        }, format='multipart')


class TemplateTests(_ImportCase):
    def test_requires_employees_create(self):
        self.assertEqual(self.client_for(self.plain).get(TEMPLATE).status_code, 403)

    def test_template_sheets_headers_and_no_sensitive_columns(self):
        response = self.client_for(self.hr).get(TEMPLATE)
        self.assertEqual(response.status_code, 200)
        workbook = openpyxl.load_workbook(io.BytesIO(response.content))
        self.assertEqual(set(workbook.sheetnames), {'Employees', 'Instructions', 'Lists'})
        headers = ' ' + ' '.join(str(c.value).lower() for c in workbook['Employees'][1])
        for forbidden in ('password', ' pan', 'aadhaar', 'bank', 'ifsc', 'uan', 'ctc', 'salary', 'face', 'token', 'key'):
            self.assertNotIn(forbidden, headers)
        self.assertEqual(len(workbook['Employees'].data_validations.dataValidation), 5)

    def test_branch_list_is_limited_for_non_admin_and_full_for_admin(self):
        def listed(user):
            workbook = openpyxl.load_workbook(io.BytesIO(self.client_for(user).get(TEMPLATE).content))
            return [row[0].value for row in workbook['Lists'].iter_rows(min_row=2, max_col=1) if row[0].value]
        self.assertEqual(listed(self.hr), ['IMP-HYD'])
        self.assertIn('IMP-BLR', listed(self.admin))
        self.assertIn('IMP-HYD', listed(self.admin))

    def test_template_round_trips_through_preview(self):
        # A filled-in template keeps its " *" header markers; the parser must accept them.
        workbook = openpyxl.load_workbook(io.BytesIO(self.client_for(self.hr).get(TEMPLATE).content))
        sheet = workbook['Employees']
        for index, value in enumerate(['Asha', 'Verma', 'asha@import.test', '2026-11-10', 'IMP-HYD', 'Import Unit', 'Analyst 1'], start=1):
            sheet.cell(row=2, column=index, value=value)
        buffer = io.BytesIO()
        workbook.save(buffer)
        response = self.client_for(self.hr).post(PREVIEW, {'file': _upload(buffer.getvalue())}, format='multipart')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['data']['can_import'])


class PreviewTests(_ImportCase):
    def test_requires_permission(self):
        self.assertEqual(self.preview(self.plain, [self.row()]).status_code, 403)

    def test_preview_is_read_only(self):
        users, audits, profiles, placements = User.objects.count(), AuditLog.objects.count(), EmployeeProfile.objects.count(), Placement.objects.count()
        response = self.preview(self.hr, [self.row(1), self.row(2)])
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertEqual(data['summary'], {'total': 2, 'valid': 2, 'invalid': 0, 'duplicate': 0})
        self.assertTrue(data['can_import'])
        self.assertEqual(
            (User.objects.count(), AuditLog.objects.count(), EmployeeProfile.objects.count(), Placement.objects.count()),
            (users, audits, profiles, placements),
        )

    def test_counts_rows_and_numbers(self):
        rows = [self.row(1), self.row(2, email='not-an-email'), self.row(3, position='Nope')]
        data = self.preview(self.hr, rows).json()['data']
        self.assertEqual(data['summary'], {'total': 3, 'valid': 1, 'invalid': 2, 'duplicate': 0})
        self.assertFalse(data['can_import'])
        self.assertEqual([r['row'] for r in data['rows']], [2, 3, 4])
        self.assertEqual([r['status'] for r in data['rows']], ['valid', 'invalid', 'invalid'])

    def test_existing_email_is_reported_as_duplicate_not_skipped(self):
        data = self.preview(self.hr, [self.row(1, email='IMP_PLAIN@test.com')]).json()['data']
        self.assertEqual(data['summary']['duplicate'], 1)
        self.assertEqual(data['rows'][0]['status'], 'duplicate')
        self.assertFalse(data['can_import'])

    def test_duplicates_inside_the_file(self):
        rows = [self.row(1, phone='9876543210'), self.row(2, email='ASHA1@import.test', phone='+91 98765-43210')]
        data = self.preview(self.hr, rows).json()['data']
        self.assertEqual(data['summary']['duplicate'], 1)
        errors = ' '.join(data['rows'][1]['errors'])
        self.assertIn('Work Email appears in row 2', errors)
        self.assertIn('Mobile Number appears in row 2', errors)

    def test_field_validation(self):
        bad = self.row(1, first_name='A$ha', date_of_joining='10/11/2026', phone='12345', employee_type='Wizard', gender='x',
                       blood_group='Z+', pin_code='12', date_of_birth='2999-01-01', personal_email='nope')
        errors = ' '.join(self.preview(self.hr, [bad]).json()['data']['rows'][0]['errors'])
        for fragment in ('First Name', 'Date of Joining', 'Mobile Number', 'Employment Type', 'Gender', 'Blood Group', 'PIN Code', 'Date of Birth', 'Personal Email'):
            self.assertIn(fragment, errors)

    def test_missing_required_values_and_missing_columns(self):
        data = self.preview(self.hr, [self.row(1, first_name='', position='')]).json()['data']
        self.assertIn('First Name is required.', data['rows'][0]['errors'])
        missing = self.preview(self.hr, [self.row(1)], headers=[h for h in HEADERS if h != 'Position'])
        self.assertEqual(missing.status_code, 400)
        self.assertIn('Position', missing.json()['message'])

    def test_unknown_branch_org_unit_and_position(self):
        rows = [self.row(1, branch='NOPE'), self.row(2, org_unit='Ghost Unit'), self.row(3, position='Ghost')]
        errors = [' '.join(r['errors']) for r in self.preview(self.admin, rows).json()['data']['rows']]
        self.assertIn('not an active branch', errors[0])
        self.assertIn('Org Unit "Ghost Unit" was not found', errors[1])
        self.assertIn('No active position', errors[2])

    def test_inactive_branch_is_refused(self):
        self.blr.status = self.blr.STATUS_INACTIVE
        self.blr.save()
        data = self.preview(self.admin, [self.row(1, branch='IMP-BLR')]).json()['data']
        self.assertFalse(data['can_import'])

    def test_occupied_seat_and_shared_seat_are_refused(self):
        make_user('holder@test.com', employee_id='IH900', branch=self.hyd.branch_name)
        Placement.objects.create(position=self.seats[2], employee=User.objects.get(email='holder@test.com'), effective_from='2020-01-01')
        rows = [self.row(1), self.row(2), self.row(3, position='Analyst 1')]
        errors = [' '.join(r['errors']) for r in self.preview(self.hr, rows).json()['data']['rows']]
        self.assertEqual(errors[0], '')
        self.assertIn('already occupied', errors[1])
        self.assertIn('used in row 2', errors[2])

    def test_full_access_position_cannot_be_imported(self):
        data = self.preview(self.admin, [self.row(1, position='Super Seat')]).json()['data']
        self.assertIn('full access', ' '.join(data['rows'][0]['errors']))

    def test_file_problems(self):
        client = self.client_for(self.hr)
        self.assertEqual(client.post(PREVIEW, {}, format='multipart').status_code, 400)
        self.assertEqual(client.post(PREVIEW, {'file': _upload(b'a,b\n1,2\n', 'x.xlsx')}, format='multipart').status_code, 400)
        self.assertEqual(client.post(PREVIEW, {'file': _upload(b'PK' + b'0' * 50, 'x.xlsx')}, format='multipart').status_code, 400)
        self.assertEqual(self.preview(self.hr, []).status_code, 400)

    def test_preview_does_not_echo_personal_details(self):
        row = self.row(1, date_of_birth='1990-01-02', address_line1='SECRET STREET', emergency_phone='9000000000', personal_email='me@example.com')
        payload = self.preview(self.hr, [row]).content.decode()
        for secret in ('SECRET STREET', '9000000000', 'me@example.com', '1990-01-02'):
            self.assertNotIn(secret, payload)


class BranchRestrictionTests(_ImportCase):
    def test_non_admin_cannot_target_another_branch_even_with_doctored_file(self):
        row = self.row(1, branch='IMP-BLR')  # the dropdown was edited in Excel
        data = self.preview(self.hr, [row]).json()['data']
        self.assertFalse(data['can_import'])
        self.assertIn('your own branch', ' '.join(data['rows'][0]['errors']))
        response = self.commit(self.hr, [row])
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email='asha1@import.test').exists())

    def test_branch_name_instead_of_code_is_also_restricted(self):
        self.assertFalse(self.preview(self.hr, [self.row(1, branch='Import Bengaluru')]).json()['data']['can_import'])
        self.assertTrue(self.preview(self.hr, [self.row(1, branch='Import Hyderabad')]).json()['data']['can_import'])

    def test_request_payload_cannot_widen_scope(self):
        # Extra form fields naming a branch or claiming admin are ignored: scope comes only from the signed-in user.
        content = _workbook([self.row(1, branch='IMP-BLR')])
        response = self.client_for(self.hr).post(COMMIT, {
            'file': _upload(content), 'batch_id': str(uuid.uuid4()), 'file_hash': file_sha256(content),
            'branch': 'IMP-BLR', 'is_admin': 'true', 'allowed_branches': 'IMP-BLR',
        }, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.filter(email='asha1@import.test').count(), 0)

    def test_non_admin_without_branch_cannot_import_anywhere(self):
        self.hr.branch = ''
        self.hr.branch_fk = None
        self.hr.save()
        self.assertFalse(self.preview(self.hr, [self.row(1)]).json()['data']['can_import'])

    def test_admin_can_import_into_any_active_branch(self):
        response = self.commit(self.admin, [self.row(1, branch='IMP-BLR'), self.row(2, branch='IMP-HYD')])
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(User.objects.get(email='asha1@import.test').branch, 'Import Bengaluru')

    def test_manager_from_another_branch_refused_for_non_admin(self):
        row = self.row(1, reporting_manager=self.blr_manager.employee_id)
        self.assertIn('own branch', ' '.join(self.preview(self.hr, [row]).json()['data']['rows'][0]['errors']))
        ok = self.row(1, reporting_manager=self.hyd_manager.employee_id)
        self.assertTrue(self.preview(self.hr, [ok]).json()['data']['can_import'])

    def test_manager_rules(self):
        ghost = self.preview(self.hr, [self.row(1, reporting_manager='NOBODY')]).json()['data']['rows'][0]['errors']
        self.assertIn('does not match an existing employee', ' '.join(ghost))
        lead_row = self.row(1, position='Team Lead', reporting_manager=self.hyd_manager.employee_id)
        self.assertIn('Managers do not have a reporting manager', ' '.join(self.preview(self.hr, [lead_row]).json()['data']['rows'][0]['errors']))


class CommitTests(_ImportCase):
    def test_requires_permission(self):
        self.assertEqual(self.commit(self.plain, [self.row()]).status_code, 403)

    def test_creates_everyone_in_one_go_and_sends_invites_after(self):
        rows = [self.row(1, phone='98765 43210', gender='Female', blood_group='b+', date_of_birth='1995-06-20', pin_code='500084',
                         employee_type='contract', address_line1='12 Main St'),
                self.row(2, reporting_manager=self.hyd_manager.employee_id)]
        with mock.patch(INVITE) as invite:
            response = self.commit(self.hr, rows)
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()['data']
        self.assertEqual((data['created'], data['invites_total'], data['invites_sent'], data['invite_failures']), (2, 2, 2, []))
        self.assertEqual(invite.call_count, 2)
        first = User.objects.get(email='asha1@import.test')
        self.assertEqual((first.full_name, first.branch, first.phone, first.employee_type, first.designation), ('Asha1 Verma', 'Import Hyderabad', '9876543210', 'Contract', 'Analyst 1'))
        self.assertTrue(first.must_change_password)
        self.assertEqual(first.onboarding_status, User.ONBOARDING_PENDING)
        self.assertTrue(Placement.objects.filter(employee=first, position=self.analyst, effective_to__isnull=True).exists())
        self.assertEqual((first.profile.gender, first.profile.blood_group, first.profile.current_pin_code), ('female', 'B+', '500084'))
        self.assertEqual(User.objects.get(email='asha2@import.test').reporting_manager_id, self.hyd_manager.pk)
        self.assertNotEqual(first.employee_id, User.objects.get(email='asha2@import.test').employee_id)
        self.assertFalse(first.has_usable_password() and first.check_password(''))

    def test_invites_are_sent_only_after_the_transaction_committed(self):
        seen = []

        def record(user, **_kw):
            seen.append(User.objects.filter(pk=user.pk).exists())
        with mock.patch(INVITE, side_effect=record):
            self.assertEqual(self.commit(self.hr, [self.row(1)]).status_code, 201)
        self.assertEqual(seen, [True])

    def test_any_invalid_row_creates_nothing(self):
        before = User.objects.count()
        response = self.commit(self.hr, [self.row(1), self.row(2, position='Nope'), self.row(3)])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['data']['created'], 0)
        self.assertEqual(User.objects.count(), before)
        self.assertFalse(AuditLog.objects.filter(action='employee_bulk_import_committed').exists())

    def test_existing_email_blocks_the_whole_import(self):
        before = User.objects.count()
        response = self.commit(self.hr, [self.row(1), self.row(2, email=self.plain.email)])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.count(), before)

    def test_failure_midway_rolls_everything_back(self):
        content = _workbook([self.row(1), self.row(2), self.row(3)])
        calls = {'n': 0}
        from apps.accounts import services_employee_import_commit as module
        original = module._save_profile

        def explode(user, result):
            calls['n'] += 1
            if calls['n'] == 3:
                raise RuntimeError('boom')
            original(user, result)
        before = (User.objects.count(), Placement.objects.count(), EmployeeProfile.objects.count())
        with mock.patch.object(module, '_save_profile', explode), mock.patch(INVITE) as invite:
            with self.assertRaises(RuntimeError):
                commit_import(self.hr, content, batch_id=str(uuid.uuid4()), expected_hash=file_sha256(content))
        self.assertEqual((User.objects.count(), Placement.objects.count(), EmployeeProfile.objects.count()), before)
        invite.assert_not_called()

    def test_file_hash_must_match_what_was_previewed(self):
        previewed = _workbook([self.row(1)])
        swapped = _workbook([self.row(1, first_name='Someone', email='other@import.test')])
        response = self.commit(self.hr, None, content=swapped, file_hash=file_sha256(previewed))
        self.assertEqual(response.status_code, 400)
        self.assertIn('not the one you previewed', response.json()['message'])
        self.assertFalse(User.objects.filter(email='other@import.test').exists())
        self.assertEqual(self.commit(self.hr, None, content=swapped, file_hash='bad').status_code, 400)

    def test_commit_revalidates_even_with_a_correct_hash(self):
        # The file was valid at preview time; an email was registered before the commit arrived.
        content = _workbook([self.row(1)])
        make_user('asha1@import.test', employee_id='IX001')
        response = self.commit(self.hr, None, content=content)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.filter(email='asha1@import.test').count(), 1)

    def test_batch_id_makes_retry_idempotent(self):
        batch = str(uuid.uuid4())
        content = _workbook([self.row(1), self.row(2)])
        with mock.patch(INVITE) as invite:
            first = self.commit(self.hr, None, batch=batch, content=content)
            second = self.commit(self.hr, None, batch=batch, content=content)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()['data']['already_committed'])
        self.assertEqual(second.json()['data']['created'], 2)
        self.assertEqual(User.objects.filter(email__endswith='@import.test').count(), 2)
        self.assertEqual(invite.call_count, 2)

    def test_batch_id_required_and_validated(self):
        content = _workbook([self.row(1)])
        client = self.client_for(self.hr)
        response = client.post(COMMIT, {'file': _upload(content), 'file_hash': file_sha256(content), 'batch_id': 'nope'}, format='multipart')
        self.assertEqual(response.status_code, 400)

    def test_invite_failure_is_reported_separately_and_keeps_the_employee(self):
        def flaky(user, **_kw):
            if user.email == 'asha2@import.test':
                raise RuntimeError('smtp down: secret-host-name')
        with mock.patch(INVITE, side_effect=flaky):
            response = self.commit(self.hr, [self.row(1), self.row(2), self.row(3)])
        self.assertEqual(response.status_code, 201)
        data = response.json()['data']
        self.assertEqual((data['created'], data['invites_sent']), (3, 2))
        self.assertEqual([f['row'] for f in data['invite_failures']], [3])
        self.assertNotIn('secret-host-name', response.content.decode())
        self.assertTrue(User.objects.filter(email='asha2@import.test').exists())

    def test_audit_has_counts_and_hash_but_no_personal_data(self):
        content = _workbook([self.row(1, phone='9876543210', address_line1='SECRET STREET')])
        with mock.patch(INVITE):
            self.commit(self.hr, None, content=content)
        entry = AuditLog.objects.get(action='employee_bulk_import_committed')
        self.assertEqual(entry.changes['created'], 1)
        self.assertEqual(entry.changes['file_sha256'], file_sha256(content))
        blob = str(entry.changes)
        for personal in ('asha1', 'Verma', '9876543210', 'SECRET STREET'):
            self.assertNotIn(personal, blob)

    def test_invite_progress_endpoint_reports_sent_and_failed(self):
        def flaky(user, **_kw):
            if user.email == 'asha2@import.test':
                raise RuntimeError('smtp down')
        batch = str(uuid.uuid4())
        with mock.patch(INVITE, side_effect=flaky):
            self.commit(self.hr, [self.row(1), self.row(2)], batch=batch)
        progress = self.client_for(self.hr).get(f'/api/employees/bulk-import/invites/{batch}/').json()['data']
        self.assertEqual((progress['state'], progress['total'], progress['sent']), ('done', 2, 1))
        self.assertEqual([f['row'] for f in progress['failed']], [3])
        self.assertNotIn('Asha', str(progress))
        self.assertEqual(self.client_for(self.admin).get(f'/api/employees/bulk-import/invites/{batch}/').status_code, 404)
        self.assertEqual(self.client_for(self.plain).get(f'/api/employees/bulk-import/invites/{batch}/').status_code, 403)

    def test_service_rejection_carries_rows(self):
        content = _workbook([self.row(1, position='Nope')])
        with self.assertRaises(ImportRejected) as caught:
            commit_import(self.hr, content, batch_id=str(uuid.uuid4()), expected_hash=file_sha256(content))
        self.assertEqual(len(caught.exception.results), 1)


class ErrorReportTests(_ImportCase):
    def report(self, user, rows):
        response = self.client_for(user).post(ERRORS, {'file': _upload(_workbook(rows))}, format='multipart')
        self.assertEqual(response.status_code, 200, response.content)
        return openpyxl.load_workbook(io.BytesIO(response.content))['Import Errors']

    def test_contains_only_problem_rows_with_errors_column(self):
        sheet = self.report(self.hr, [self.row(1), self.row(2, position='Nope'), self.row(3, email='bad')])
        headers = [c.value for c in sheet[1]]
        self.assertIn('Import Errors', headers)
        self.assertEqual(sheet.max_row, 3)
        emails = [sheet.cell(row=r, column=headers.index('Work Email *') + 1).value for r in (2, 3)]
        self.assertEqual(emails, ['asha2@import.test', 'bad'])
        self.assertIn('No active position', sheet.cell(row=2, column=headers.index('Import Errors') + 1).value)

    def test_has_no_personal_or_sensitive_data(self):
        row = self.row(1, position='Nope', phone='9876543210', date_of_birth='1990-01-02', address_line1='SECRET STREET',
                       emergency_phone='9000000000', personal_email='me@example.com', gender='Female', reporting_manager='IM001')
        sheet = self.report(self.hr, [row])
        text = ' '.join(str(cell.value) for line in sheet.iter_rows() for cell in line)
        headers = [c.value for c in sheet[1]]
        for secret in ('SECRET STREET', '9000000000', 'me@example.com', '1990-01-02', '9876543210'):
            self.assertNotIn(secret, text)
        for header in ('Date of Birth', 'Personal Email', 'Gender', 'Address Line 1', 'Emergency Contact Number', 'Mobile Number'):
            self.assertNotIn(header, ' '.join(str(h) for h in headers))

    def test_formula_like_text_is_neutralised(self):
        sheet = self.report(self.hr, [self.row(1, first_name='+cmd|calc', position='Nope')])
        value = sheet.cell(row=2, column=1).value
        self.assertTrue(value.startswith("'"), value)

    def test_requires_permission(self):
        response = self.client_for(self.plain).post(ERRORS, {'file': _upload(_workbook([self.row()]))}, format='multipart')
        self.assertEqual(response.status_code, 403)


class ExistingFlowsUntouchedTests(_ImportCase):
    def test_old_bulk_import_and_single_create_routes_still_exist(self):
        from django.urls import reverse
        for name in ('employee-bulk-import', 'employee-bulk-import-sample', 'employee-list-create'):
            self.assertTrue(reverse(name))
        self.assertEqual(self.client_for(self.plain).post('/api/employees/bulk-import/', {}, format='multipart').status_code, 403)
