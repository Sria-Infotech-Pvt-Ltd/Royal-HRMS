"""UAT-051: one approver route (manager -> reporting approver -> branch HR -> company admin), configurable, with skipped stages recorded."""
import datetime

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.services_reporting_line import resolve_approver_route
from apps.hrms.models import REQ_L2_PENDING, LeaveBalance, LeavePolicy, LeaveRequest


def _admin(email, code):
    return make_user(email, employee_id=code, branch='Mulugu', role=make_role(f'admin_{code}', permission_codenames=['settings.edit', 'leave.approve']))


class ApproverRouteTests(TestCase):
    def setUp(self):
        cache.clear()
        self.employee = make_user('route.worker@test.com', employee_id='EMPAR001', branch='Kondapur')
        self.admin = _admin('route.admin@test.com', 'EMPAR090')

    def test_manager_comes_first(self):
        manager = make_user('route.mgr@test.com', employee_id='EMPAR002')
        self.employee.reporting_manager = manager
        self.employee.save()
        route = resolve_approver_route(self.employee)
        self.assertEqual((route.user, route.source, route.skipped), (manager, 'reporting_manager', ()))

    def test_then_the_reporting_approver_then_hr_then_the_company_admin(self):
        approver = make_user('route.approver@test.com', employee_id='EMPAR003')
        hr = make_user('route.hr@test.com', employee_id='EMPAR004')
        self.employee.reporting_approver = approver
        self.employee.save()
        self.assertEqual(resolve_approver_route(self.employee).source, 'reporting_approver')
        self.assertEqual(resolve_approver_route(self.employee).skipped, ('reporting_manager',))

        self.employee.reporting_approver = None
        self.employee.hr = hr
        self.employee.save()
        route = resolve_approver_route(self.employee)
        self.assertEqual((route.user, route.source, route.skipped), (hr, 'branch_hr', ('reporting_manager', 'reporting_approver')))

        self.employee.hr = None
        self.employee.save()
        route = resolve_approver_route(self.employee)
        self.assertEqual((route.user, route.source), (self.admin, 'company_admin'))
        self.assertIn('routed to the company HR/admin', route.skipped_note())

    def test_nobody_anywhere_is_reported_not_hidden(self):
        lonely_admin_only = make_user('route.only@test.com', employee_id='EMPAR005')
        route = resolve_approver_route(lonely_admin_only, exclude_sources=('company_admin',))
        self.assertIsNone(route.user)
        self.assertIn('nobody else could approve', route.skipped_note())

    def test_the_employee_is_never_their_own_approver(self):
        self.assertNotEqual(resolve_approver_route(self.admin).user, self.admin)

    @override_settings(APPROVER_FALLBACK_ORDER=['company_admin', 'reporting_manager'])
    def test_the_order_is_configurable(self):
        manager = make_user('route.mgr2@test.com', employee_id='EMPAR006')
        self.employee.reporting_manager = manager
        self.employee.save()
        self.assertEqual(resolve_approver_route(self.employee).source, 'company_admin')

    @override_settings(APPROVER_FALLBACK_ORDER=['nonsense'])
    def test_unknown_names_fall_back_to_the_default_order(self):
        self.assertEqual(resolve_approver_route(self.employee).source, 'company_admin')


class LeaveWithoutManagerTests(TestCase):
    def setUp(self):
        cache.clear()
        LeavePolicy.objects.update_or_create(
            leave_type='casual',
            defaults={'annual_days': 4, 'is_active': True, 'minimum_notice_period': 0, 'maximum_consecutive_days': 0,
                      'minimum_service_period': 0, 'applicable_gender': 'all'},
        )
        _admin('leave.route.admin@test.com', 'EMPLR090')
        self.employee = make_user('leave.nomgr@test.com', employee_id='EMPLR001', branch='Kondapur')  # no manager, no HR assigned
        day = datetime.date(2030, 3, 4)
        LeaveBalance.objects.create(employee=self.employee, leave_type='casual', year=2030, total_days=4, used_days=0)
        self.client = APIClient()
        self.client.force_authenticate(user=self.employee)
        self.day = day

    def test_a_request_without_a_manager_reaches_a_real_approver_and_says_why(self):
        response = self.client.post(reverse('leave-request-list'), {
            'leave_type': 'casual', 'duration': 'full_day', 'start_date': self.day.isoformat(), 'end_date': self.day.isoformat(),
            'reason': 'Personal family work',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.json())
        data = response.json()['data']
        self.assertEqual(data['status'], REQ_L2_PENDING)
        self.assertTrue(data['l1_skipped'])
        self.assertEqual(data['l1_remarks'], 'Manager stage skipped - no manager assigned.')
        self.assertTrue(data['l2_approver_name'])  # a real person decides, not "Not yet assigned"
        self.assertTrue(LeaveRequest.objects.get(pk=data['id']).l2_approver_id)
