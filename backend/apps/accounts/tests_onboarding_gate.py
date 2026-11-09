"""
The onboarding gate (audit finding G1) and its split into two independent checks.

  * HasCompletedOnboardingStatus — a candidate-portal user (requires_self_service_onboarding, onboarding_status pending /
    draft / submitted / rejected) is limited to the onboarding wizard until HR approves them. Applied to the employee-portal
    modules: leave, expenses, attendance (self-service), payroll self-service, performance self-service, employee
    documents, announcements, work-from-home, separation, the HR helpdesk and referrals.
  * HasClearedAssessments — an employee with assessments still pending (assessment_status == pending).
  * HasCompletedOnboarding — both together. Unchanged for the dashboard/work-status views that already used it.

A pending assessment therefore does NOT lock an otherwise completed employee out of the modules above (the web proxy
still redirects them to the assessments page). The wizard and its required uploads, Face ID registration, notifications
and authentication are never gated. Superusers, `employees.view` holders and team managers are exempt from all three.

Probes are read-only GETs and empty-body POSTs, so nothing is created. The per-object routes (approve, acknowledge,
react, ...) are probed with ids that do not exist: the gate answers before any lookup, so a blocked user gets the gate's
403 and an exempt user gets an ordinary 404/400.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import User
from core.permissions import HasClearedAssessments, HasCompletedOnboarding, HasCompletedOnboardingStatus

INCOMPLETE = (User.ONBOARDING_PENDING, User.ONBOARDING_DRAFT, User.ONBOARDING_SUBMITTED, User.ONBOARDING_REJECTED)
STATUS_MESSAGE = HasCompletedOnboardingStatus.message
COMBINED_MESSAGE = HasCompletedOnboarding.message

COMBINED_READS = [  # the views that already used the combined gate before G1
    '/api/dashboard/employee/kpis/', '/api/dashboard/employee/leave-balances/', '/api/dashboard/birthdays/mine/',
    '/api/work-status/me/',
]
STATUS_READS = [
    # leave and expenses
    '/api/leave/balance/', '/api/leave/stats/', '/api/leave/requests/', '/api/leave/policy/', '/api/leave/holidays/',
    '/api/expenses/', '/api/expenses/categories/', '/api/expenses/stats/',
    # attendance (self-service)
    '/api/attendance/today/', '/api/attendance/my-shift/', '/api/attendance/my-weekly-timesheet/',
    '/api/attendance/stats/', '/api/attendance/summary/', '/api/attendance/calendar/',
    '/api/attendance/recent-punches/', '/api/attendance/corrections/my/',
    # payroll and performance self-service
    '/api/payroll/my-payslips/', '/api/payroll/tax-declarations/schema/', '/api/payroll/tax-declarations/me/',
    '/api/performance/reviews/me/', '/api/performance/goals/me/', '/api/performance/feedback-requests/',
    '/api/performance/feedback-requests/colleagues/',
    # employee documents and announcements
    '/api/documents/', '/api/documents/stats/', '/api/announcements/', '/api/dashboard/announcement/',
    # work-from-home, separation, HR helpdesk, referrals
    '/api/wfh/requests/', '/api/separation/types/', '/api/separation/reasons/', '/api/separation/requests/',
    '/api/hr-help/requests/', '/api/recruitment/referrals/', '/api/recruitment/referral-rules/',
    '/api/recruitment/referral-bonuses/',
]
STATUS_WRITES = [  # empty body: the gate must answer before the endpoint's own validation
    '/api/leave/requests/', '/api/expenses/', '/api/attendance/punch/', '/api/attendance/correction/',
    '/api/attendance/geofence-check/', '/api/payroll/tax-declarations/me/submit/', '/api/performance/reviews/me/submit/',
    '/api/performance/feedback-requests/', '/api/documents/',
    '/api/wfh/requests/', '/api/separation/requests/', '/api/hr-help/requests/', '/api/recruitment/referrals/',
]
VALIDATION_WRITES = [  # an employee reaches the endpoint's own validation (400) with an empty body; nothing is created
    '/api/leave/requests/', '/api/expenses/', '/api/wfh/requests/', '/api/separation/requests/', '/api/hr-help/requests/',
    '/api/recruitment/referrals/',
]
ZERO_UUID = '00000000-0000-0000-0000-000000000001'
STATUS_OBJECT_ROUTES = [  # (method, url): changed views that the list/collection probes above do not reach
    ('post', f'/api/leave/requests/{ZERO_UUID}/approve/'), ('get', f'/api/leave/requests/{ZERO_UUID}/'),
    ('post', '/api/leave/requests/record/'), ('patch', f'/api/leave/balance/{ZERO_UUID}/'),
    ('get', '/api/leave/calendar/'), ('get', f'/api/leave/holidays/{ZERO_UUID}/'),
    ('get', '/api/expenses/999999/'), ('get', '/api/expenses/status/'),
    ('post', f'/api/payroll/my-payslips/{ZERO_UUID}/acknowledge/'), ('post', f'/api/payroll/my-payslips/{ZERO_UUID}/log-download/'),
    ('get', f'/api/payroll/my-payslips/{ZERO_UUID}/pdf/'), ('get', '/api/payroll/my-payslips/form16/2025/pdf/'),
    ('get', f'/api/performance/goals/me/{ZERO_UUID}/'), ('post', f'/api/performance/reviews/{ZERO_UUID}/acknowledge/'),
    ('post', f'/api/performance/feedback-requests/{ZERO_UUID}/respond/'),
    ('get', '/api/announcements/999999/'), ('post', '/api/announcements/999999/react/'), ('post', '/api/announcements/999999/view/'),
    ('get', '/api/documents/999999/'),
    # work-from-home, separation, helpdesk, referrals
    ('get', f'/api/wfh/requests/{ZERO_UUID}/'), ('post', f'/api/wfh/requests/{ZERO_UUID}/approve/'),
    ('get', f'/api/separation/requests/{ZERO_UUID}/'), ('get', f'/api/separation/requests/{ZERO_UUID}/tasks/'),
    ('get', f'/api/separation/requests/{ZERO_UUID}/clearances/'), ('get', f'/api/separation/requests/{ZERO_UUID}/settlement/'),
    ('post', f'/api/separation/requests/{ZERO_UUID}/settlement/finalize/'), ('get', f'/api/separation/requests/{ZERO_UUID}/documents/'),
    ('get', f'/api/separation/requests/{ZERO_UUID}/activities/'), ('get', f'/api/hr-help/requests/{ZERO_UUID}/'),
    ('get', '/api/recruitment/referrals/all/'), ('get', '/api/recruitment/referral-rules/999999/'),
    ('get', '/api/recruitment/referral-bonuses/999999/'), ('post', '/api/recruitment/referral-bonuses/999999/approve/'),
    ('post', '/api/recruitment/referral-bonuses/999999/pay/'),
]
OPEN_READS = [  # must stay reachable while onboarding
    '/api/onboarding/', '/api/onboarding/step/0/', '/api/onboarding/documents/', '/api/onboarding/custom-file-fields/',
    '/api/notifications/', '/api/notifications/unread-count/', '/api/attendance/face-registration/me/',
    '/api/attendance/face-verification/status/',
]


def _api(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class GateFixtures(TestCase):
    """Candidates in every incomplete status, a completed employee, and the helpers the test classes share."""

    def setUp(self):
        cache.clear()
        # work-status falls back to an external service when credentials are configured; without them it returns
        # before any network call, which is what a test must do.
        credentials = patch('apps.hrms.services_project_sync._credentials', return_value=None)
        credentials.start()
        self.addCleanup(credentials.stop)
        self.candidates = {
            status: make_user(f'gate_{status}@test.com', employee_id=f'GT{index}', requires_self_service_onboarding=True, onboarding_status=status)
            for index, status in enumerate(INCOMPLETE)
        }
        self.completed = make_user(
            'gate_complete@test.com', employee_id='GT9', requires_self_service_onboarding=True, onboarding_status=User.ONBOARDING_COMPLETE,
        )
        # Otherwise-completed employee whose assessments are still pending (assigned after hire or approval).
        self.assessing = make_user(
            'gate_assessing@test.com', employee_id='GT8', onboarding_status=User.ONBOARDING_COMPLETE,
            assessment_status=User.ASSESSMENT_PENDING,
        )

    def _blocked(self, response, message=STATUS_MESSAGE) -> bool:
        return response.status_code == 403 and response.json().get('message') == message

    def _blocked_by_any_gate(self, response) -> bool:
        return self._blocked(response, STATUS_MESSAGE) or self._blocked(response, COMBINED_MESSAGE)

    def _exempt_users(self) -> dict:
        """Users who would be blocked on BOTH checks if the exemption did not apply: portal flag on, onboarding not
        complete, assessments pending."""
        def build(email, employee_id, role=None, **extra):
            return make_user(
                email, role=role, employee_id=employee_id, requires_self_service_onboarding=True,
                onboarding_status=User.ONBOARDING_PENDING, assessment_status=User.ASSESSMENT_PENDING, **extra,
            )
        return {
            'hr': build('exempt_hr@test.com', 'EH1', role=make_role('exempt_hr', permission_codenames=['employees.view'])),
            'team manager': build('exempt_mgr@test.com', 'EM1', role=make_role('exempt_mgr', can_manage_team=True)),
            'superuser': build('exempt_root@test.com', 'ER1', is_superuser=True),
        }


class OnboardingGateTests(GateFixtures):
    # ── blocked: unapproved candidates ────────────────────────────────────────

    def test_incomplete_candidates_get_403_on_every_status_gated_read(self):
        for status, user in self.candidates.items():
            for url in STATUS_READS:
                self.assertTrue(self._blocked(_api(user).get(url)), (status, url))

    def test_incomplete_candidates_get_403_on_status_gated_writes_before_validation(self):
        for status, user in self.candidates.items():
            for url in STATUS_WRITES:
                self.assertTrue(self._blocked(_api(user).post(url, {}, format='json')), (status, url))

    def test_incomplete_candidates_stay_blocked_on_the_combined_gate_views(self):
        for status, user in self.candidates.items():
            for url in COMBINED_READS:
                self.assertTrue(self._blocked(_api(user).get(url), COMBINED_MESSAGE), (status, url))

    # ── unaffected ────────────────────────────────────────────────────────────

    def test_completed_employees_still_reach_every_gated_read(self):
        for url in STATUS_READS + COMBINED_READS:
            response = _api(self.completed).get(url)
            self.assertFalse(self._blocked_by_any_gate(response), url)
            self.assertEqual(response.status_code, 200, url)

    def test_completed_employees_still_reach_a_write_endpoint_validation(self):
        for url in VALIDATION_WRITES:
            response = _api(self.completed).post(url, {}, format='json')
            self.assertEqual(response.status_code, 400, url)  # the endpoint's own validation, nothing created

    def test_hr_team_managers_and_superusers_are_exempt_from_every_gate(self):
        for label, user in self._exempt_users().items():
            for url in STATUS_READS + COMBINED_READS:
                self.assertFalse(self._blocked_by_any_gate(_api(user).get(url)), (label, url))

    # ── the assessment separation ─────────────────────────────────────────────

    def test_a_pending_assessment_does_not_block_an_otherwise_completed_employee_on_the_status_gated_routes(self):
        for url in STATUS_READS:
            response = _api(self.assessing).get(url)
            self.assertFalse(self._blocked_by_any_gate(response), url)
            self.assertEqual(response.status_code, 200, url)
        for url in VALIDATION_WRITES:
            self.assertEqual(_api(self.assessing).post(url, {}, format='json').status_code, 400, url)

    def test_a_pending_assessment_still_blocks_the_combined_gate_views(self):
        for url in COMBINED_READS:
            self.assertTrue(self._blocked(_api(self.assessing).get(url), COMBINED_MESSAGE), url)

    # ── stays open ────────────────────────────────────────────────────────────

    def test_wizard_uploads_notifications_and_face_registration_stay_open_while_onboarding(self):
        for status, user in self.candidates.items():
            for url in OPEN_READS:
                response = _api(user).get(url)
                self.assertFalse(self._blocked_by_any_gate(response), (status, url))
                self.assertEqual(response.status_code, 200, (status, url))

    def test_the_required_upload_routes_are_not_gated_for_writes(self):
        for status, user in self.candidates.items():
            for url in ('/api/onboarding/documents/', '/api/onboarding/custom-file-fields/', '/api/attendance/face-registration/'):
                response = _api(user).post(url, {}, format='multipart')
                self.assertFalse(self._blocked_by_any_gate(response), (status, url))

    def test_login_is_not_gated(self):
        response = APIClient().post('/api/login/', {}, format='json')
        self.assertEqual(response.status_code, 400)  # validation of the empty body, not the gate


class GatedObjectRouteTests(GateFixtures):
    def _call(self, user, method, url):
        return getattr(_api(user), method)(url, {}, format='json')

    def test_incomplete_candidates_get_403_on_every_per_object_route(self):
        for status, user in self.candidates.items():
            for method, url in STATUS_OBJECT_ROUTES:
                self.assertTrue(self._blocked(self._call(user, method, url)), (status, method, url))

    def test_hr_team_managers_and_superusers_are_not_blocked_on_the_per_object_routes(self):
        for label, user in self._exempt_users().items():
            for method, url in STATUS_OBJECT_ROUTES:
                self.assertFalse(self._blocked_by_any_gate(self._call(user, method, url)), (label, method, url))

    def test_completed_employees_are_not_blocked_on_the_per_object_routes(self):
        for method, url in STATUS_OBJECT_ROUTES:
            self.assertFalse(self._blocked_by_any_gate(self._call(self.completed, method, url)), (method, url))

    def test_a_pending_assessment_does_not_block_the_per_object_routes(self):
        for method, url in STATUS_OBJECT_ROUTES:
            self.assertFalse(self._blocked_by_any_gate(self._call(self.assessing, method, url)), (method, url))


class PermissionClassTests(GateFixtures):
    """The three classes directly: (status, assessments, combined) for each kind of user."""

    def _verdicts(self, user) -> tuple:
        request = SimpleNamespace(user=user)
        return tuple(
            permission().has_permission(request, None)
            for permission in (HasCompletedOnboardingStatus, HasClearedAssessments, HasCompletedOnboarding)
        )

    def test_unapproved_candidate_fails_only_the_status_check(self):
        self.assertEqual(self._verdicts(self.candidates[User.ONBOARDING_PENDING]), (False, True, False))

    def test_pending_assessment_fails_only_the_assessment_check(self):
        self.assertEqual(self._verdicts(self.assessing), (True, False, False))

    def test_a_candidate_with_a_pending_assessment_fails_both(self):
        user = make_user(
            'gate_both@test.com', employee_id='GT7', requires_self_service_onboarding=True,
            onboarding_status=User.ONBOARDING_SUBMITTED, assessment_status=User.ASSESSMENT_PENDING,
        )
        self.assertEqual(self._verdicts(user), (False, False, False))

    def test_a_completed_employee_passes_all_three(self):
        self.assertEqual(self._verdicts(self.completed), (True, True, True))

    def test_hr_team_managers_and_superusers_pass_all_three_even_when_flagged(self):
        for label, user in self._exempt_users().items():
            self.assertEqual(self._verdicts(user), (True, True, True), label)

    def test_anonymous_users_fail_all_three(self):
        self.assertEqual(self._verdicts(AnonymousUser()), (False, False, False))

    def test_the_combined_gate_keeps_its_original_message(self):
        self.assertEqual(COMBINED_MESSAGE, 'Complete onboarding and your assigned assessments before accessing this resource.')
        self.assertNotEqual(STATUS_MESSAGE, COMBINED_MESSAGE)
