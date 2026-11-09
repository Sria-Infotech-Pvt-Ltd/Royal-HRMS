"""
Friday MVP lifecycle: the HAND-OFFS between stages, not the stages in isolation.

Two entry paths exist in the product (TEAM_CONTEXT.md, "Workflow rule"):

  A. Hire Employee wizard (HR-only):  HR enters everything, onboarding is complete at hire, the employee gets an invite,
     sets a password, logs in once and is active.  There is NO employee submission and NO HR approval on this path.
  B. Candidate portal (Interview List): the employee fills the onboarding wizard and submits, HR approves or rejects.

The Friday sentence ("hire -> invite -> set password -> complete onboarding -> HR approves -> activate") spans both, so each
path is exercised separately and the shared tail (profile -> attendance -> leave -> decision) runs on path A.

Leave balances: hire completion ALLOCATES the joining-year balance (pro-rata, rounded to 0.5, see
_allocate_leaves_for_employee). HR can top it up with PATCH /api/leave/balance/<id>/. POST /api/leave/balance/ only creates
rows that do not exist yet (for example another year). Later years come from the year-start and monthly accrual jobs.

External boundaries are mocked: SMTP (message building/sending) and ImageKit storage. Everything else is real: tokens,
password setting, cookie login, permissions, punches, leave balance and approval.
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

import apps.accounts.tests_hire_wizard as wizard
from apps.accounts.factories import make_role, make_user
from apps.accounts.models import EmailLog, OnboardingEvent, OrgUnit, PasswordResetToken, Position, User
from apps.attendance.models import AttendancePunch
from apps.hrms.models import REQ_APPROVED, REQ_L2_PENDING, REQ_REJECTED, LeaveBalance, LeavePolicy, LeaveRequest

NEW_PASSWORD = 'LifeCycle#2026x'
SHARED = 'apps.accounts.views.shared'
FIRST_DAY, SECOND_DAY = datetime.date(2030, 3, 4), datetime.date(2030, 3, 5)  # Monday and Tuesday


def _login(client: APIClient, email: str, password: str = NEW_PASSWORD):
    response = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert response.status_code == 200, response.json()
    return response


class _EmailBoundary:
    """Mixin: SMTP is mocked at the message-building/sending boundary; tokens and EmailLog rows stay real."""

    def _mock_email(self):
        smtp = patch('apps.accounts.utils._get_smtp_connection', return_value=(None, 'noreply@test.com', None))
        build = patch('apps.accounts.utils._build_message')
        template_mail = patch('apps.accounts.utils.send_template_email')  # notification mails (e.g. leave decisions)
        smtp.start()
        built = build.start()
        template_mail.start()
        built.return_value.send.return_value = None
        self.addCleanup(smtp.stop)
        self.addCleanup(build.stop)
        self.addCleanup(template_mail.stop)


class _HireLifecycleBase(_EmailBoundary, wizard.HireWizardTestCase):
    """Shared setUp and helpers for the hire-based lifecycle classes. Has no tests of its own."""

    def setUp(self):
        super().setUp()  # HR user, position, ImageKit storage stand-in
        self._mock_email()
        LeavePolicy.objects.update_or_create(
            leave_type='casual',
            defaults={'annual_days': 4, 'is_active': True, 'minimum_notice_period': 0, 'maximum_consecutive_days': 0,
                      'minimum_service_period': 0, 'applicable_gender': 'all', 'allow_probation_leave': True},
        )
        manager_profile = make_role('lc_manager', permission_codenames=['leave.approve', 'leave.view'], can_manage_team=True)
        self.manager = make_user('lc_manager@test.com', role=manager_profile, employee_id='LCM001', password=NEW_PASSWORD)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _hire(self) -> User:
        action = self._create_draft()
        self._set_employment_type(action, 'Permanent')
        self._patch(action, self._valid_full_draft())
        self._upload_all_required_docs(action)
        response = self._complete(action)
        self.assertEqual(response.status_code, 201, f'step 1 (HR hire): {response.data}')
        return User.objects.get(employee_id=response.data['data']['reserved_employee_id'])

    def _activate(self, employee: User) -> APIClient:
        # Hire requires a future joining date; by the time this employee applies for leave their joining date has arrived
        # (Pre-Joining employees cannot request leave, see services_lifecycle_status).
        User.objects.filter(pk=employee.pk).update(date_of_joining=datetime.date.today())
        token = PasswordResetToken.objects.filter(user=employee, purpose=PasswordResetToken.PURPOSE_INVITE).latest('created_at')
        self.assertEqual(APIClient().get(reverse('invite-check', args=[token.id])).status_code, 200, 'step 4 (open invite link)')
        response = APIClient().post(reverse('reset-password'), {
            'reset_token': str(token.id), 'new_password': NEW_PASSWORD, 'confirm_password': NEW_PASSWORD,
        }, format='json')
        self.assertEqual(response.status_code, 200, f'step 4 (set password): {response.json()}')
        client = APIClient()
        _login(client, employee.email)
        return client

    def _leave_day_in_joining_year(self, employee: User) -> datetime.date:
        """A Monday-Friday on or after tomorrow that is still in the joining year (that is the year hire allocates)."""
        day = max(employee.date_of_joining, datetime.date.today() + datetime.timedelta(days=1))
        while day.weekday() >= 5:
            day += datetime.timedelta(days=1)
        if day.year != employee.date_of_joining.year:
            self.skipTest('Joining date is in the last days of the year: no working day left in the allocated year.')
        return day

    def _apply_leave(self, client: APIClient, day: datetime.date):
        return client.post(reverse('leave-request-list'), {
            'leave_type': 'casual', 'duration': 'full_day', 'start_date': day.isoformat(), 'end_date': day.isoformat(),
            'reason': 'Personal family work',
        }, format='json')


class HireToLeaveLifecycleTests(_HireLifecycleBase):
    """Path A end to end: HR hire -> invite -> password -> first login -> profile -> punch -> leave -> manager decision."""

    # ── the lifecycle ─────────────────────────────────────────────────────────

    def test_hire_to_approved_leave_end_to_end(self):
        employee = self._hire()
        # steps 1-2: employee exists, onboarding is complete by design on this path, invite issued and logged
        self.assertTrue(employee.is_active and employee.activation_pending)
        self.assertEqual(employee.onboarding_status, User.ONBOARDING_COMPLETE)
        self.assertIsNone(employee.account_activated_at)
        self.assertTrue(EmailLog.objects.filter(recipient_email=employee.email, template_name='onboarding_invite', status=EmailLog.STATUS_SENT).exists(), 'step 2 (invite email logged as sent)')

        # steps 3-5: password via the link, then the first login activates the account
        client = self._activate(employee)
        employee.refresh_from_db()
        self.assertFalse(employee.activation_pending, 'step 5 (activation after first login)')
        self.assertIsNotNone(employee.account_activated_at)
        self.assertTrue(employee.is_onboarded())
        self.assertTrue(OnboardingEvent.objects.filter(employee=employee, event=OnboardingEvent.ACTIVATED).exists())

        # step 6: own profile
        profile = client.get(reverse('my-profile'))
        self.assertEqual(profile.status_code, 200, f'step 6 (own profile): {profile.json()}')

        # step 7: punch in and out, history shows it
        self.assertEqual(client.post(reverse('attendance-punch'), {'punch_type': 'IN', 'attendance_mode': 'office'}, format='json').status_code, 200, 'step 7 (punch in)')
        self.assertEqual(client.post(reverse('attendance-punch'), {'punch_type': 'OUT', 'attendance_mode': 'office'}, format='json').status_code, 200, 'step 7 (punch out)')
        self.assertEqual(AttendancePunch.objects.filter(employee=employee).count(), 2)
        history = client.get(reverse('attendance-recent-punches'))
        self.assertEqual(history.status_code, 200)
        self.assertTrue(history.json()['data'], 'step 8 (attendance history is not empty)')

        # step 9: leave on a fixed future date. Hire only allocates the JOINING year, so the 2030 row is created directly
        # here; the joining-year allocation and HR top-up are tested separately below.
        User.objects.filter(pk=employee.pk).update(reporting_manager=self.manager)
        LeaveBalance.objects.create(employee=employee, leave_type='casual', year=FIRST_DAY.year, total_days=4, used_days=0)
        applied = self._apply_leave(client, FIRST_DAY)
        self.assertEqual(applied.status_code, 201, f'step 9 (apply for leave): {applied.json()}')
        request_id = applied.json()['data']['id']
        listing = client.get(reverse('leave-request-list'))
        self.assertIn(request_id, [row['id'] for row in listing.json()['data']['results']], 'step 9 (employee sees own request)')

        # steps 10-12: manager approves, status and balance update
        manager_client = APIClient()
        _login(manager_client, self.manager.email)
        decision = manager_client.post(reverse('leave-request-approve', args=[request_id]), {'action': 'approve'}, format='json')
        self.assertEqual(decision.status_code, 200, f'step 10 (manager approves): {decision.json()}')
        leave = LeaveRequest.objects.get(pk=request_id)
        self.assertEqual(leave.status, REQ_APPROVED)
        balance = LeaveBalance.objects.get(employee=employee, leave_type='casual', year=FIRST_DAY.year)
        self.assertEqual(float(balance.used_days), 1.0, 'step 11 (balance deducted)')
        again = client.get(reverse('leave-request-list')).json()['data']['results']
        self.assertEqual({row['id']: row['status'] for row in again}[request_id], REQ_APPROVED, 'step 12 (employee sees the decision)')

    def test_a_rejected_leave_keeps_the_balance(self):
        employee = self._hire()
        client = self._activate(employee)
        User.objects.filter(pk=employee.pk).update(reporting_manager=self.manager)
        LeaveBalance.objects.create(employee=employee, leave_type='casual', year=SECOND_DAY.year, total_days=4, used_days=0)
        request_id = self._apply_leave(client, SECOND_DAY).json()['data']['id']
        manager_client = APIClient()
        _login(manager_client, self.manager.email)
        decision = manager_client.post(reverse('leave-request-approve', args=[request_id]), {'action': 'reject', 'remarks': 'Team is short that day'}, format='json')
        self.assertEqual(decision.status_code, 200, decision.json())
        self.assertEqual(LeaveRequest.objects.get(pk=request_id).status, REQ_REJECTED)
        balance = LeaveBalance.objects.get(employee=employee, leave_type='casual', year=SECOND_DAY.year)
        self.assertEqual(float(balance.used_days), 0.0)
        status_after = {row['id']: row['status'] for row in client.get(reverse('leave-request-list')).json()['data']['results']}
        self.assertEqual(status_after[request_id], REQ_REJECTED)

    def test_hire_allocates_the_joining_year_balance_with_the_existing_pro_rata_rule(self):
        """Documents the rule that already exists (annual_days x months left / 12, rounded to 0.5); it is not changed here."""
        employee = self._hire()
        balance = LeaveBalance.objects.get(employee=employee, leave_type='casual', year=employee.date_of_joining.year)
        expected = Decimal(str(round(4 * (13 - employee.date_of_joining.month) / 12 * 2) / 2))
        self.assertEqual(balance.total_days, expected)
        self.assertEqual(balance.used_days, 0)

    def test_hire_allocates_only_the_joining_year_so_a_later_year_has_no_balance_yet(self):
        employee = self._hire()
        client = self._activate(employee)
        response = self._apply_leave(client, FIRST_DAY)  # 2030: later years come from the year-start / monthly jobs
        self.assertEqual(response.status_code, 400)
        self.assertIn('No leave balance found', response.json()['message'])

    def test_the_credit_endpoint_creates_a_balance_for_a_year_that_has_no_row(self):
        """POST /api/leave/balance/ (leave.approve) creates MISSING rows only; the request then goes through."""
        employee = self._hire()
        client = self._activate(employee)
        User.objects.filter(pk=employee.pk).update(reporting_manager=self.manager)
        self.assertEqual(self._apply_leave(client, FIRST_DAY).status_code, 400)
        credit_client = APIClient()
        _login(credit_client, self.manager.email)
        credited = credit_client.post('/api/leave/balance/', {'employee_id': employee.employee_id, 'year': FIRST_DAY.year}, format='json')
        self.assertEqual(credited.status_code, 200, credited.json())
        self.assertEqual(float(LeaveBalance.objects.get(employee=employee, leave_type='casual', year=FIRST_DAY.year).total_days), 4.0)
        self.assertEqual(self._apply_leave(client, FIRST_DAY).status_code, 201)

    def test_a_new_hire_on_probation_is_refused_unless_the_policy_allows_probation_leave(self):
        """Policy default (allow_probation_leave=False) refuses a probationary new hire; the lifecycle test sets it True."""
        LeavePolicy.objects.filter(leave_type='casual').update(allow_probation_leave=False)
        employee = self._hire()
        client = self._activate(employee)
        LeaveBalance.objects.create(employee=employee, leave_type='casual', year=FIRST_DAY.year, total_days=4, used_days=0)
        response = self._apply_leave(client, FIRST_DAY)
        self.assertEqual(response.status_code, 400)
        self.assertIn('probation', response.json()['message'].lower())

    # ── invite edge cases ─────────────────────────────────────────────────────

    def test_invalid_expired_and_reused_invite_links_are_refused(self):
        employee = self._hire()
        self.assertEqual(APIClient().get(reverse('invite-check', args=['00000000-0000-0000-0000-000000000009'])).status_code, 404)
        token = PasswordResetToken.objects.filter(user=employee, purpose=PasswordResetToken.PURPOSE_INVITE).latest('created_at')
        PasswordResetToken.objects.filter(pk=token.pk).update(expires_at=timezone.now() - datetime.timedelta(hours=1))
        self.assertEqual(APIClient().get(reverse('invite-check', args=[token.id])).status_code, 410)
        expired = APIClient().post(reverse('reset-password'), {
            'reset_token': str(token.id), 'new_password': NEW_PASSWORD, 'confirm_password': NEW_PASSWORD,
        }, format='json')
        self.assertEqual(expired.status_code, 400)
        PasswordResetToken.objects.filter(pk=token.pk).update(expires_at=timezone.now() + datetime.timedelta(hours=1))
        self._activate(employee)
        reused = APIClient().post(reverse('reset-password'), {
            'reset_token': str(token.id), 'new_password': NEW_PASSWORD, 'confirm_password': NEW_PASSWORD,
        }, format='json')
        self.assertEqual(reused.status_code, 400)

    def test_login_before_setting_a_password_is_refused(self):
        employee = self._hire()
        response = APIClient().post(reverse('login'), {'email': employee.email, 'password': 'guess-Wrong1!'}, format='json')
        self.assertEqual(response.status_code, 401)


class HrLeaveApprovalLifecycleTests(_HireLifecycleBase):
    """
    HR as the approver. The employee has no reporting manager, so the manager stage is skipped and the request waits at
    L2 for the employee's designated HR (User.hr). The intended permission is `leave.approve`; at L2 only the
    designated HR may act (any same-branch `leave.approve` holder only when no HR is assigned).

    Friday HR steps under test: hire already allocates the joining-year balance (pro-rata). If it is too small, HR tops it up
    with PATCH /api/leave/balance/<id>/. For a year with no row HR can create it with POST /api/leave/balance/. Whether the
    existing pro-rata / accrual rule is the intended one is a deferred decision; nothing here changes it.
    """

    def setUp(self):
        super().setUp()
        self.branch = self._valid_full_draft()['branch']
        approve = ['leave.approve', 'leave.view']
        self.hr = self._hr('lc_hr_approver@test.com', 'LCH010', approve, self.branch)
        self.other_hr = self._hr('lc_hr_other@test.com', 'LCH011', approve, self.branch)  # same branch, not the designated HR
        self.other_branch_hr = self._hr('lc_hr_elsewhere@test.com', 'LCH012', approve, 'Another Branch')
        self.hr_without_permission = self._hr('lc_hr_viewonly@test.com', 'LCH013', ['leave.view', 'employees.view'], self.branch)

    def _hr(self, email, employee_id, permissions, branch) -> User:
        role = make_role(f'role_{employee_id}', permission_codenames=permissions)
        return make_user(email, role=role, employee_id=employee_id, password=NEW_PASSWORD, branch=branch)

    def _client(self, user: User) -> APIClient:
        client = APIClient()
        _login(client, user.email)
        return client

    def _hired_with_balance(self):
        """Hire, activate, assign the designated HR, then HR creates the (future-year) 2030 balance row."""
        employee = self._hire()
        employee_client = self._activate(employee)
        User.objects.filter(pk=employee.pk).update(hr=self.hr, reporting_manager=None)
        credited = self._client(self.hr).post('/api/leave/balance/', {'employee_id': employee.employee_id, 'year': FIRST_DAY.year}, format='json')
        self.assertEqual(credited.status_code, 200, f'HR creates the 2030 balance: {credited.json()}')
        return employee, employee_client

    def _used_days(self, employee: User) -> float:
        return float(LeaveBalance.objects.get(employee=employee, leave_type='casual', year=FIRST_DAY.year).used_days)

    def _request_waiting_for_hr(self, employee_client: APIClient, day: datetime.date) -> str:
        applied = self._apply_leave(employee_client, day)
        self.assertEqual(applied.status_code, 201, applied.json())
        return applied.json()['data']['id']

    def test_hr_approves_the_request_status_and_balance_update(self):
        employee, employee_client = self._hired_with_balance()
        request_id = self._request_waiting_for_hr(employee_client, FIRST_DAY)
        leave = LeaveRequest.objects.get(pk=request_id)
        self.assertEqual(leave.status, REQ_L2_PENDING)
        self.assertEqual(leave.l2_approver_id, self.hr.id, 'the designated HR of the employee is the approver')
        self.assertEqual(self._used_days(employee), 0.0, 'nothing is deducted while the request is pending')

        decision = self._client(self.hr).post(reverse('leave-request-approve', args=[request_id]), {'action': 'approve'}, format='json')
        self.assertEqual(decision.status_code, 200, decision.json())
        self.assertEqual(LeaveRequest.objects.get(pk=request_id).status, REQ_APPROVED)
        self.assertEqual(self._used_days(employee), 1.0)
        seen = {row['id']: row['status'] for row in employee_client.get(reverse('leave-request-list')).json()['data']['results']}
        self.assertEqual(seen[request_id], REQ_APPROVED, 'the employee sees the decision')

    def test_hr_rejects_the_request_and_the_balance_is_untouched(self):
        employee, employee_client = self._hired_with_balance()
        request_id = self._request_waiting_for_hr(employee_client, FIRST_DAY)
        decision = self._client(self.hr).post(
            reverse('leave-request-approve', args=[request_id]), {'action': 'reject', 'remarks': 'Needs a different date'}, format='json',
        )
        self.assertEqual(decision.status_code, 200, decision.json())
        self.assertEqual(LeaveRequest.objects.get(pk=request_id).status, REQ_REJECTED)
        self.assertEqual(self._used_days(employee), 0.0)
        seen = {row['id']: row['status'] for row in employee_client.get(reverse('leave-request-list')).json()['data']['results']}
        self.assertEqual(seen[request_id], REQ_REJECTED)

    def test_hr_without_leave_approve_cannot_decide_and_the_request_is_unchanged(self):
        employee, employee_client = self._hired_with_balance()
        request_id = self._request_waiting_for_hr(employee_client, FIRST_DAY)
        for action in ('approve', 'reject'):
            response = self._client(self.hr_without_permission).post(reverse('leave-request-approve', args=[request_id]), {'action': action}, format='json')
            self.assertEqual(response.status_code, 403, action)
        self.assertEqual(LeaveRequest.objects.get(pk=request_id).status, REQ_L2_PENDING)
        self.assertEqual(self._used_days(employee), 0.0)

    def test_only_the_designated_hr_may_decide_other_hr_users_are_refused(self):
        employee, employee_client = self._hired_with_balance()
        request_id = self._request_waiting_for_hr(employee_client, FIRST_DAY)
        for label, user in (('same-branch HR, not designated', self.other_hr), ('HR of another branch', self.other_branch_hr)):
            response = self._client(user).post(reverse('leave-request-approve', args=[request_id]), {'action': 'approve'}, format='json')
            self.assertEqual(response.status_code, 403, label)
        self.assertEqual(LeaveRequest.objects.get(pk=request_id).status, REQ_L2_PENDING)
        self.assertEqual(self._used_days(employee), 0.0)

    def test_hr_tops_up_a_too_small_allocated_balance_then_the_request_is_approved(self):
        """The real Friday case: current-year dates, the balance hire allocated is smaller than a full day."""
        employee = self._hire()
        employee_client = self._activate(employee)
        User.objects.filter(pk=employee.pk).update(hr=self.hr, reporting_manager=None)
        day = self._leave_day_in_joining_year(employee)
        balance = LeaveBalance.objects.get(employee=employee, leave_type='casual', year=day.year)
        LeaveBalance.objects.filter(pk=balance.pk).update(total_days=Decimal('0.5'))  # what a late-in-year joiner gets

        refused = self._apply_leave(employee_client, day)
        self.assertEqual(refused.status_code, 400)
        self.assertIn('insufficient balance', refused.json()['message'].lower())

        topped_up = self._client(self.hr).patch(f'/api/leave/balance/{balance.id}/', {'total_days': 4}, format='json')
        self.assertEqual(topped_up.status_code, 200, topped_up.json())
        self.assertEqual(float(LeaveBalance.objects.get(pk=balance.pk).total_days), 4.0)

        request_id = self._apply_leave(employee_client, day).json()['data']['id']
        self.assertEqual(LeaveRequest.objects.get(pk=request_id).status, REQ_L2_PENDING)
        decision = self._client(self.hr).post(reverse('leave-request-approve', args=[request_id]), {'action': 'approve'}, format='json')
        self.assertEqual(decision.status_code, 200, decision.json())
        balance.refresh_from_db()
        self.assertEqual(float(balance.used_days), 1.0)

    def test_hr_without_leave_approve_cannot_top_up_a_balance(self):
        employee = self._hire()
        balance = LeaveBalance.objects.get(employee=employee, leave_type='casual', year=employee.date_of_joining.year)
        before = balance.total_days
        response = self._client(self.hr_without_permission).patch(f'/api/leave/balance/{balance.id}/', {'total_days': 40}, format='json')
        self.assertEqual(response.status_code, 403)
        balance.refresh_from_db()
        self.assertEqual(balance.total_days, before)

    def test_hr_without_leave_approve_cannot_create_the_balance_either(self):
        employee = self._hire()
        response = self._client(self.hr_without_permission).post(
            '/api/leave/balance/', {'employee_id': employee.employee_id, 'year': FIRST_DAY.year}, format='json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(LeaveBalance.objects.filter(employee=employee, year=FIRST_DAY.year).exists())


class CandidatePortalLifecycleTests(TestCase):
    """Path B: candidate-portal user -> first login/password change -> gated -> wizard submit -> HR approve/reject."""

    TEMP_PASSWORD = 'TempPortal#1'

    def setUp(self):
        cache.clear()
        hr_profile = make_role('lc_onboarding_hr', permission_codenames=['onboarding.approve', 'settings.edit'])
        self.hr = make_user('lc_hr@test.com', role=hr_profile, employee_id='LCH001', password=NEW_PASSWORD)
        self.position = Position.objects.create(org_unit=OrgUnit.objects.create(name='Lifecycle Engineering'), title='Engineer', grade='L2')

    def _candidate(self, email: str) -> User:
        return make_user(
            email, password=self.TEMP_PASSWORD, must_change_password=True, requires_self_service_onboarding=True,
            onboarding_status=User.ONBOARDING_PENDING, assessment_status=User.ASSESSMENT_COMPLETE, account_activated_at=None,
            full_name='Portal Candidate',
        )

    def _submit(self, client: APIClient):
        with patch(f'{SHARED}._step_required_configs', return_value=[]):
            self.assertEqual(client.patch('/api/onboarding/step/0/', {'gender': 'male'}, format='json').status_code, 200)
        for name in ('_missing_required', '_missing_education_experience', '_missing_required_docs'):
            patcher = patch(f'{SHARED}.{name}', return_value=[])
            patcher.start()
            self.addCleanup(patcher.stop)
        face = patch('apps.attendance.services_face_policy.can_employee_self_register', return_value=False)
        face.start()
        self.addCleanup(face.stop)
        return client.post('/api/onboarding/', {}, format='json')

    def _first_login_and_password_change(self, candidate: User) -> APIClient:
        client = APIClient()
        _login(client, candidate.email, self.TEMP_PASSWORD)
        changed = client.post(reverse('change-password'), {
            'old_password': self.TEMP_PASSWORD, 'new_password': NEW_PASSWORD, 'confirm_password': NEW_PASSWORD,
        }, format='json')
        self.assertEqual(changed.status_code, 200, changed.json())
        client = APIClient()
        _login(client, candidate.email)
        return client

    def test_candidate_submits_hr_approves_and_the_modules_open(self):
        candidate = self._candidate('lc_candidate@test.com')
        client = self._first_login_and_password_change(candidate)
        candidate.refresh_from_db()
        self.assertIsNotNone(candidate.account_activated_at)

        # before approval: the onboarding gate keeps the candidate out of the employee modules
        blocked = client.get('/api/leave/balance/')
        self.assertEqual(blocked.status_code, 403, 'step 3 (gate before approval)')
        self.assertEqual(client.get('/api/onboarding/').status_code, 200, 'wizard stays reachable')

        submitted = self._submit(client)
        self.assertEqual(submitted.status_code, 200, f'step 3 (employee submits): {submitted.json()}')
        candidate.refresh_from_db()
        self.assertEqual(candidate.onboarding_status, User.ONBOARDING_SUBMITTED)

        hr_client = APIClient()
        _login(hr_client, self.hr.email)
        approved = hr_client.post(reverse('onboarding-approve', args=[candidate.id]), {'decision': 'approve', 'position': str(self.position.id)}, format='json')
        self.assertEqual(approved.status_code, 200, f'step 4 (HR approves): {approved.json()}')
        candidate.refresh_from_db()
        self.assertEqual(candidate.onboarding_status, User.ONBOARDING_COMPLETE)
        self.assertTrue(candidate.employee_id, 'an employee number is issued at approval')

        # after approval: same session, the modules are open
        opened = client.get('/api/leave/balance/')
        self.assertEqual(opened.status_code, 200, f'step 5 (gate released after approval): {opened.json()}')
        self.assertEqual(client.get(reverse('my-profile')).status_code, 200)

    def test_hr_rejection_keeps_the_candidate_gated_and_records_the_remarks(self):
        candidate = self._candidate('lc_rejected@test.com')
        client = self._first_login_and_password_change(candidate)
        self.assertEqual(self._submit(client).status_code, 200)
        hr_client = APIClient()
        _login(hr_client, self.hr.email)
        rejected = hr_client.post(reverse('onboarding-approve', args=[candidate.id]), {'decision': 'reject', 'remarks': 'Documents unclear'}, format='json')
        self.assertEqual(rejected.status_code, 200, rejected.json())
        candidate.refresh_from_db()
        self.assertEqual(candidate.onboarding_status, User.ONBOARDING_REJECTED)
        self.assertEqual(candidate.onboarding_rejection_remarks, 'Documents unclear')
        self.assertEqual(client.get('/api/leave/balance/').status_code, 403)


class EmployeeIsolationTests(_EmailBoundary, TestCase):
    """DoD 6 and 11: a plain employee cannot read another employee's profile, attendance or leave."""

    def setUp(self):
        cache.clear()
        self._mock_email()
        LeavePolicy.objects.update_or_create(
            leave_type='casual',
            defaults={'annual_days': 4, 'is_active': True, 'minimum_notice_period': 0, 'maximum_consecutive_days': 0,
                      'minimum_service_period': 0, 'applicable_gender': 'all', 'allow_probation_leave': True},
        )
        # Someone must be able to decide the request: a leave request is no longer accepted when nobody could approve it.
        make_user('iso_approver@test.com', role=make_role('iso_leave_approver', permission_codenames=['leave.approve']), employee_id='ISO009', password=NEW_PASSWORD, branch='Kondapur')
        self.alice = make_user('iso_alice@test.com', employee_id='ISO001', password=NEW_PASSWORD, branch='Kondapur')
        self.bob = make_user('iso_bob@test.com', employee_id='ISO002', password=NEW_PASSWORD, branch='Kondapur')
        self.alice_client, self.bob_client = APIClient(), APIClient()
        _login(self.alice_client, self.alice.email)
        _login(self.bob_client, self.bob.email)
        self.alice_client.post(reverse('attendance-punch'), {'punch_type': 'IN', 'attendance_mode': 'office'}, format='json')
        LeaveBalance.objects.create(employee=self.alice, leave_type='casual', year=FIRST_DAY.year, total_days=4, used_days=0)
        applied = self.alice_client.post(reverse('leave-request-list'), {
            'leave_type': 'casual', 'duration': 'full_day', 'start_date': FIRST_DAY.isoformat(), 'end_date': FIRST_DAY.isoformat(),
            'reason': 'Personal family work',
        }, format='json')
        self.assertEqual(applied.status_code, 201, applied.json())
        self.alice_request = applied.json()['data']['id']

    def test_bob_cannot_read_alices_profile(self):
        self.assertEqual(self.alice_client.get(f'/api/employees/{self.alice.employee_id}/').status_code, 200)  # self is allowed
        self.assertIn(self.bob_client.get(f'/api/employees/{self.alice.employee_id}/').status_code, (403, 404))

    def test_bob_cannot_read_alices_attendance(self):
        for url in ('/api/attendance/calendar/', '/api/attendance/summary/', '/api/attendance/stats/', '/api/attendance/recent-punches/'):
            response = self.bob_client.get(url, {'employee_id': self.alice.employee_id})
            self.assertIn(response.status_code, (403, 404), url)
        own = self.bob_client.get('/api/attendance/recent-punches/')  # without the parameter Bob only ever sees himself
        self.assertEqual(own.json()['data'], [])

    def test_bob_cannot_read_or_decide_alices_leave(self):
        listing = self.bob_client.get('/api/leave/requests/')
        self.assertEqual(listing.status_code, 200)
        self.assertNotIn(self.alice_request, [row['id'] for row in listing.json()['data']['results']])
        self.assertIn(self.bob_client.get(f'/api/leave/requests/{self.alice_request}/').status_code, (403, 404))
        self.assertEqual(self.bob_client.get('/api/leave/requests/', {'employee_id': self.alice.employee_id}).status_code, 403)
        self.assertEqual(self.bob_client.get('/api/leave/stats/', {'employee_id': self.alice.employee_id}).status_code, 403)
        # The balance list ignores employee_id for a caller without employees.view: Bob gets HIS OWN balances (none), never Alice's.
        balances = self.bob_client.get('/api/leave/balance/', {'employee_id': self.alice.employee_id})
        self.assertEqual(balances.status_code, 200)
        self.assertEqual(balances.json()['data'], [])
        decision = self.bob_client.post(reverse('leave-request-approve', args=[self.alice_request]), {'action': 'approve'}, format='json')
        self.assertEqual(decision.status_code, 403)
        self.assertNotIn(LeaveRequest.objects.get(pk=self.alice_request).status, (REQ_APPROVED, REQ_REJECTED))  # still undecided
