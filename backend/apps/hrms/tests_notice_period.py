"""
Notice-period countdown (starts only at final separation approval) and the
branch-scoped access rules on the Separation APIs.
"""
from __future__ import annotations

import datetime

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.hrms.models import (
    APPROVAL_APPROVED, APPROVAL_PENDING, APPROVAL_REJECTED,
    SEP_APPROVED, SEP_CANCELLED, SEP_CLEARANCE_HR, SEP_PENDING, SEP_REJECTED, SEP_STAGE2_PENDING,
    SEP_STAGE_HR, SEP_STAGE_MANAGER,
    SeparationApprovalStage, SeparationClearance, SeparationRequest,
)
from apps.hrms.services_notice import NOTICE_COMPLETED, NOTICE_SERVING, notice_info
from config.test_runner import TEST_COMPANY_CODE

PASSWORD = 'TestPass123!'
HYD = 'Hyderabad Notice'
MUM = 'Mumbai Notice'

EMPLOYEE_NOTICE_URL = '/api/dashboard/employee/notice-period/'
HR_LIFECYCLE_URL = '/api/dashboard/hr/employee-lifecycle/'
ADMIN_LIFECYCLE_URL = '/api/dashboard/system-admin/employee-lifecycle/'


def _today() -> datetime.date:
    return timezone.localdate()


class _FakeRequest:
    def __init__(self, status, last_day):
        self.status = status
        self.proposed_last_working_day = last_day
        self.approval_stages = self

    def all(self):
        return []


class NoticeInfoBoundaryTests(SimpleTestCase):
    TODAY = datetime.date(2026, 10, 9)

    def test_future_last_working_day_is_serving_with_days_left(self):
        info = notice_info(_FakeRequest(SEP_APPROVED, datetime.date(2026, 10, 14)), self.TODAY)
        self.assertEqual(info['notice_status'], NOTICE_SERVING)
        self.assertEqual(info['days_remaining'], 5)

    def test_last_working_day_today_is_zero_days_and_still_serving(self):
        info = notice_info(_FakeRequest(SEP_APPROVED, self.TODAY), self.TODAY)
        self.assertEqual(info['notice_status'], NOTICE_SERVING)
        self.assertEqual(info['days_remaining'], 0)

    def test_past_last_working_day_is_completed(self):
        info = notice_info(_FakeRequest(SEP_APPROVED, datetime.date(2026, 10, 8)), self.TODAY)
        self.assertEqual(info['notice_status'], NOTICE_COMPLETED)
        self.assertEqual(info['days_remaining'], 0)

    def test_no_countdown_unless_approved(self):
        for status in (SEP_PENDING, SEP_STAGE2_PENDING, SEP_REJECTED, SEP_CANCELLED):
            with self.subTest(status=status):
                self.assertIsNone(notice_info(_FakeRequest(status, self.TODAY), self.TODAY))


class _NoticeFixtures(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.sysadmin = make_user(
            'notice.sysadmin@test.com', role=make_role('system_admin', permission_codenames=['settings.edit', 'employees.view']),
            employee_id='EMPNSA01', full_name='Notice SysAdmin', branch=HYD,
        )
        branch_hr_role = make_role('notice_branch_hr', permission_codenames=['employees.view', 'separation.approve'])
        self.hr_hyd = make_user('notice.hr.hyd@test.com', role=branch_hr_role, employee_id='EMPNHH01', full_name='HR Hyd', branch=HYD)
        self.hr_mum = make_user('notice.hr.mum@test.com', role=branch_hr_role, employee_id='EMPNHM01', full_name='HR Mum', branch=MUM)

        self.staff_role = make_role('notice_staff')
        self.emp_hyd = self._employee('notice.emp.hyd@test.com', 'EMPNEH01', 'Hyd Employee', HYD)
        self.emp_hyd2 = self._employee('notice.emp.hyd2@test.com', 'EMPNEH02', 'Hyd Employee Two', HYD)
        self.emp_mum = self._employee('notice.emp.mum@test.com', 'EMPNEM01', 'Mum Employee', MUM)

    def _employee(self, email, employee_id, name, branch, **extra):
        return make_user(
            email, role=self.staff_role, employee_id=employee_id, full_name=name, branch=branch,
            department='Ops', onboarding_status='complete', assessment_status='complete', **extra,
        )

    def _login(self, user):
        resp = self.client.post(
            reverse('login'), {'company_code': TEST_COMPANY_CODE, 'email': user.email, 'password': PASSWORD},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)

    def _request(self, employee, status, last_day, request_date=None, approved_at=None, stage_approver=None):
        sep = SeparationRequest.objects.create(
            employee=employee, separation_type='resignation', reason='personal_reason',
            request_date=request_date or (_today() - datetime.timedelta(days=10)),
            proposed_last_working_day=last_day, notice_period_days=30, status=status,
        )
        first = {SEP_PENDING: APPROVAL_PENDING, SEP_REJECTED: APPROVAL_REJECTED}.get(status, APPROVAL_APPROVED)
        second = APPROVAL_APPROVED if status == SEP_APPROVED else APPROVAL_PENDING
        approved_at = approved_at or timezone.now()
        SeparationApprovalStage.objects.create(
            request=sep, stage=SEP_STAGE_MANAGER, sequence=1, status=first, approver=stage_approver,
            actioned_at=None if first == APPROVAL_PENDING else approved_at - datetime.timedelta(days=1),
        )
        SeparationApprovalStage.objects.create(
            request=sep, stage=SEP_STAGE_HR, sequence=2, status=second,
            actioned_at=approved_at if second == APPROVAL_APPROVED else None,
        )
        return sep

    def _detail(self, sep):
        return self.client.get(reverse('separation-request-detail', kwargs={'request_id': str(sep.id)}))


class SeparationNoticeFieldsTests(_NoticeFixtures):
    def test_pending_rejected_cancelled_and_stage2_have_no_countdown(self):
        self._login(self.sysadmin)
        for status in (SEP_PENDING, SEP_STAGE2_PENDING, SEP_REJECTED, SEP_CANCELLED):
            with self.subTest(status=status):
                sep = self._request(self.emp_hyd, status, _today() + datetime.timedelta(days=20))
                data = self._detail(sep).data['data']
                self.assertIsNone(data['approved_at'])
                self.assertIsNone(data['confirmed_last_working_day'])
                self.assertIsNone(data['notice_status'])
                self.assertIsNone(data['days_remaining'])
                sep.delete()

    def test_countdown_starts_only_at_final_approval_through_the_real_workflow(self):
        last_day = _today() + datetime.timedelta(days=21)
        self._login(self.hr_hyd)
        resp = self.client.post(reverse('separation-request-list'), {
            'employee_id': self.emp_hyd.employee_id, 'separation_type': 'resignation', 'reason': 'personal_reason',
            'request_date': (_today() - datetime.timedelta(days=9)).isoformat(),
            'proposed_last_working_day': last_day.isoformat(), 'notice_period_days': 30,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        sep_id = resp.data['data']['id']
        self.assertIsNone(resp.data['data']['notice_status'])

        self._login(self.sysadmin)
        stages = list(SeparationApprovalStage.objects.filter(request_id=sep_id).order_by('sequence'))
        first = self.client.post(
            reverse('separation-stage-action', kwargs={'request_id': sep_id, 'stage_id': str(stages[0].id)}),
            {'action': 'approve'}, format='json',
        )
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data['data']['status'], SEP_STAGE2_PENDING)
        self.assertIsNone(first.data['data']['days_remaining'])

        final = self.client.post(
            reverse('separation-stage-action', kwargs={'request_id': sep_id, 'stage_id': str(stages[1].id)}),
            {'action': 'approve'}, format='json',
        )
        self.assertEqual(final.status_code, 200, final.data)
        data = final.data['data']
        stages[1].refresh_from_db()
        self.assertEqual(data['status'], SEP_APPROVED)
        self.assertEqual(data['approved_at'], timezone.localtime(stages[1].actioned_at).isoformat())
        self.assertEqual(data['confirmed_last_working_day'], last_day.isoformat())
        self.assertEqual(data['proposed_last_working_day'], last_day.isoformat())
        self.assertEqual(data['notice_status'], NOTICE_SERVING)
        self.assertEqual(data['days_remaining'], 21)


class EmployeeNoticeDashboardTests(_NoticeFixtures):
    def test_no_approved_request_returns_null(self):
        self._request(self.emp_hyd, SEP_PENDING, _today() + datetime.timedelta(days=5))
        self._login(self.emp_hyd)
        resp = self.client.get(EMPLOYEE_NOTICE_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['data']['notice_period'])

    def test_own_approved_request_shows_countdown(self):
        sep = self._request(self.emp_hyd, SEP_APPROVED, _today() + datetime.timedelta(days=7))
        self._login(self.emp_hyd)
        data = self.client.get(EMPLOYEE_NOTICE_URL).data['data']['notice_period']
        self.assertEqual(data['request_id'], str(sep.id))
        self.assertEqual(data['notice_status'], NOTICE_SERVING)
        self.assertEqual(data['days_remaining'], 7)
        self.assertEqual(data['confirmed_last_working_day'], (_today() + datetime.timedelta(days=7)).isoformat())
        self.assertIsNotNone(data['approved_at'])

    def test_last_day_today_and_past(self):
        self._request(self.emp_hyd, SEP_APPROVED, _today())
        self._request(self.emp_hyd2, SEP_APPROVED, _today() - datetime.timedelta(days=1))

        self._login(self.emp_hyd)
        today_data = self.client.get(EMPLOYEE_NOTICE_URL).data['data']['notice_period']
        self.assertEqual((today_data['notice_status'], today_data['days_remaining']), (NOTICE_SERVING, 0))

        self._login(self.emp_hyd2)
        past_data = self.client.get(EMPLOYEE_NOTICE_URL).data['data']['notice_period']
        self.assertEqual(past_data['notice_status'], NOTICE_COMPLETED)

    def test_employee_never_sees_another_employees_notice(self):
        self._request(self.emp_hyd2, SEP_APPROVED, _today() + datetime.timedelta(days=7))
        self._login(self.emp_hyd)
        self.assertIsNone(self.client.get(EMPLOYEE_NOTICE_URL).data['data']['notice_period'])

    def test_completed_notice_does_not_deactivate_employee(self):
        self._request(self.emp_hyd, SEP_APPROVED, _today() - datetime.timedelta(days=3))
        self._login(self.emp_hyd)
        self.client.get(EMPLOYEE_NOTICE_URL)
        self.emp_hyd.refresh_from_db()
        self.assertTrue(self.emp_hyd.is_active)


class NoticeLifecycleDashboardTests(_NoticeFixtures):
    def setUp(self):
        super().setUp()
        self.serving_hyd = self._request(self.emp_hyd, SEP_APPROVED, _today() + datetime.timedelta(days=4))
        self.today_hyd = self._request(self.emp_hyd2, SEP_APPROVED, _today())
        self.serving_mum = self._request(self.emp_mum, SEP_APPROVED, _today() + datetime.timedelta(days=9))
        for email, eid, status, offset in (
            ('notice.pend@test.com', 'EMPNXP01', SEP_PENDING, 5),
            ('notice.rej@test.com', 'EMPNXR01', SEP_REJECTED, 5),
            ('notice.can@test.com', 'EMPNXC01', SEP_CANCELLED, 5),
            ('notice.past@test.com', 'EMPNXD01', SEP_APPROVED, -1),
        ):
            self._request(self._employee(email, eid, eid, HYD), status, _today() + datetime.timedelta(days=offset))
        inactive = self._employee('notice.inactive@test.com', 'EMPNXI01', 'Inactive', HYD)
        self._request(inactive, SEP_APPROVED, _today() + datetime.timedelta(days=3))
        inactive.is_active = False
        inactive.save(update_fields=['is_active'])

    def _ids(self, payload):
        return [e['request_id'] for e in payload['notice_period']['employees']]

    def test_branch_hr_sees_only_own_branch_currently_serving(self):
        self._login(self.hr_hyd)
        resp = self.client.get(HR_LIFECYCLE_URL)
        self.assertEqual(resp.status_code, 200)
        data = resp.data['data']
        self.assertEqual(self._ids(data), [str(self.today_hyd.id), str(self.serving_hyd.id)])
        self.assertEqual(data['notice_period']['count'], 2)
        row = next(e for e in data['notice_period']['employees'] if e['request_id'] == str(self.serving_hyd.id))
        self.assertEqual(row['employee_id'], self.emp_hyd.employee_id)
        self.assertEqual(row['department'], 'Ops')
        self.assertEqual(row['branch'], HYD)
        self.assertEqual(row['days_remaining'], 4)
        self.assertEqual(row['last_working_day'], (_today() + datetime.timedelta(days=4)).isoformat())
        self.assertIsNotNone(row['approved_at'])

    def test_cached_lifecycle_still_shows_fresh_notice_and_per_branch(self):
        self._login(self.hr_mum)
        self.assertEqual(self._ids(self.client.get(HR_LIFECYCLE_URL).data['data']), [str(self.serving_mum.id)])
        self._login(self.hr_hyd)  # same shared cache entry, different branch
        self.assertNotIn(str(self.serving_mum.id), self._ids(self.client.get(HR_LIFECYCLE_URL).data['data']))

        new_sep = self._request(self._employee('notice.new@test.com', 'EMPNXN01', 'New', HYD), SEP_APPROVED,
                                _today() + datetime.timedelta(days=30))
        self.assertIn(str(new_sep.id), self._ids(self.client.get(HR_LIFECYCLE_URL).data['data']))

    def test_system_admin_sees_all_branches(self):
        self._login(self.sysadmin)
        ids = self._ids(self.client.get(ADMIN_LIFECYCLE_URL).data['data'])
        self.assertCountEqual(ids, [str(self.today_hyd.id), str(self.serving_hyd.id), str(self.serving_mum.id)])


class SeparationBranchAccessTests(_NoticeFixtures):
    def _create_payload(self, employee):
        return {
            'employee_id': employee.employee_id, 'separation_type': 'resignation', 'reason': 'personal_reason',
            'request_date': _today().isoformat(),
            'proposed_last_working_day': (_today() + datetime.timedelta(days=30)).isoformat(),
            'notice_period_days': 30,
        }

    def test_branch_user_can_initiate_for_own_branch(self):
        self._login(self.hr_hyd)
        resp = self.client.post(reverse('separation-request-list'), self._create_payload(self.emp_hyd), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_branch_user_cannot_initiate_for_other_branch(self):
        self._login(self.hr_hyd)
        resp = self.client.post(reverse('separation-request-list'), self._create_payload(self.emp_mum), format='json')
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(SeparationRequest.objects.filter(employee=self.emp_mum).exists())

    def test_system_admin_can_initiate_for_any_branch(self):
        self._login(self.sysadmin)
        resp = self.client.post(reverse('separation-request-list'), self._create_payload(self.emp_mum), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_cannot_initiate_for_inactive_employee(self):
        self.emp_hyd.is_active = False
        self.emp_hyd.save(update_fields=['is_active'])
        self._login(self.hr_hyd)
        resp = self.client.post(reverse('separation-request-list'), self._create_payload(self.emp_hyd), format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(SeparationRequest.objects.filter(employee=self.emp_hyd).exists())

    def test_duplicate_active_request_still_blocked(self):
        self._request(self.emp_hyd, SEP_APPROVED, _today() + datetime.timedelta(days=5))
        self._login(self.hr_hyd)
        resp = self.client.post(reverse('separation-request-list'), self._create_payload(self.emp_hyd), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_detail_is_branch_scoped(self):
        mum_sep = self._request(self.emp_mum, SEP_PENDING, _today() + datetime.timedelta(days=5))
        hyd_sep = self._request(self.emp_hyd, SEP_PENDING, _today() + datetime.timedelta(days=5))
        self._login(self.hr_hyd)
        self.assertEqual(self._detail(mum_sep).status_code, 404)
        self.assertEqual(self._detail(hyd_sep).status_code, 200)
        self._login(self.sysadmin)
        self.assertEqual(self._detail(mum_sep).status_code, 200)

    def test_named_approver_keeps_access_across_branches(self):
        mum_sep = self._request(self.emp_mum, SEP_PENDING, _today() + datetime.timedelta(days=5), stage_approver=self.hr_hyd)
        self._login(self.hr_hyd)
        self.assertEqual(self._detail(mum_sep).status_code, 200)

    def test_list_by_employee_id_is_branch_scoped(self):
        self._request(self.emp_mum, SEP_PENDING, _today() + datetime.timedelta(days=5))
        self._login(self.hr_hyd)
        resp = self.client.get(reverse('separation-request-list'), {'employee_id': self.emp_mum.employee_id})
        self.assertEqual(resp.status_code, 404)

    def test_sub_endpoints_are_branch_scoped(self):
        mum_sep = self._request(self.emp_mum, SEP_APPROVED, _today() + datetime.timedelta(days=5))
        clearance = SeparationClearance.objects.create(request=mum_sep, clearance_type=SEP_CLEARANCE_HR)
        self._login(self.hr_hyd)
        self.assertEqual(
            self.client.get(reverse('separation-clearance-list', kwargs={'request_id': str(mum_sep.id)})).status_code, 404,
        )
        resp = self.client.post(
            reverse('separation-clearance-action', kwargs={'request_id': str(mum_sep.id), 'clearance_id': str(clearance.id)}),
            {'action': 'approve'}, format='json',
        )
        self.assertEqual(resp.status_code, 403)
        clearance.refresh_from_db()
        self.assertEqual(clearance.status, APPROVAL_PENDING)

        self._login(self.hr_mum)
        resp = self.client.post(
            reverse('separation-clearance-action', kwargs={'request_id': str(mum_sep.id), 'clearance_id': str(clearance.id)}),
            {'action': 'approve'}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_employee_sees_own_request_but_not_others(self):
        own = self._request(self.emp_hyd, SEP_PENDING, _today() + datetime.timedelta(days=5))
        other = self._request(self.emp_hyd2, SEP_PENDING, _today() + datetime.timedelta(days=5))
        self._login(self.emp_hyd)
        self.assertEqual(self._detail(own).status_code, 200)
        self.assertEqual(self._detail(other).status_code, 403)
        listed = self.client.get(reverse('separation-request-list')).data['data']['results']
        self.assertEqual([r['id'] for r in listed], [str(own.id)])
