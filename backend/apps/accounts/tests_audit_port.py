"""
Access-control fixes ported from the Backend/24/08/2026 audit onto the current code.

Each test proves one gap is closed AND that the people who legitimately use the screen still get through, because the old branch
could not be merged and several of its hunks would have broken today's pages (those were deliberately NOT ported; see TEAM_CONTEXT).
"""
from __future__ import annotations

import datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.tests_employee_scope import make_branch
from apps.payroll.models import PayrollCycle
from apps.payroll.views.ecr import _get_authorized_cycle
from apps.recruitment.models import Candidate

PASSWORD = 'TestPass123!'


def _client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class DocumentsNeedTheViewPermissionTests(TestCase):
    def setUp(self):
        self.user = make_user('audit_docs@test.com', role=make_role('audit_docs_role'), password=PASSWORD)

    def test_list_stats_and_detail_refuse_a_caller_without_documents_view(self):
        with patch('apps.accounts.views.documents._has_perm', return_value=False):
            for name, kwargs in (('document-list-create', {}), ('document-stats', {}), ('document-detail', {'pk': '1'})):
                with self.subTest(view=name):
                    self.assertEqual(_client(self.user).get(reverse(name, kwargs=kwargs)).status_code, 403)

    def test_everyone_keeps_access_because_documents_view_is_a_baseline_permission(self):
        # Not patched: a plain employee holds documents.view through the baseline, so the Documents page keeps working.
        self.assertEqual(_client(self.user).get(reverse('document-list-create')).status_code, 200)
        self.assertEqual(_client(self.user).get(reverse('document-stats')).status_code, 200)

    def test_a_signed_download_link_still_works_without_the_permission(self):
        from django.core import signing
        token = signing.dumps({'id': 1}, salt='doc-dl')
        with patch('apps.accounts.views.documents._has_perm', return_value=False):
            response = APIClient().get(reverse('document-detail', kwargs={'pk': '1'}), {'t': token})
        self.assertNotEqual(response.status_code, 403)   # authenticated by the token (a missing file answers 404, not 403)


class BirthdaySettingsWriteTests(TestCase):
    def test_read_only_employee_visibility_cannot_change_the_company_wide_automation(self):
        viewer = make_user('audit_bday_view@test.com', role=make_role('audit_bday_view', permission_codenames=['employees.view']))
        response = _client(viewer).patch(reverse('birthday-settings'), {'is_enabled': False}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_settings_edit_can_change_it(self):
        admin = make_user('audit_bday_admin@test.com', role=make_role('audit_bday_admin', permission_codenames=['settings.edit', 'employees.view']))
        response = _client(admin).patch(reverse('birthday-settings'), {'is_enabled': False}, format='json')
        self.assertEqual(response.status_code, 200, response.data)


class AttendanceOneEmployeeScopeTests(TestCase):
    def setUp(self):
        self.viewer = make_user('audit_att_view@test.com', role=make_role('audit_att_view', permission_codenames=['attendance.view']))
        self.employee = make_user('audit_att_emp@test.com', role=make_role('audit_att_emp'), employee_id='AUD0001')

    def test_month_and_weekly_off_history_refuse_an_employee_the_viewer_may_not_see(self):
        with patch('apps.attendance.views.employee_month._manager_can_access_employee', return_value=False), \
                patch('apps.attendance.views.weekly_off._manager_can_access_employee', return_value=False):
            month = _client(self.viewer).get(reverse('hr-employee-month-calendar'), {'employee_id': str(self.employee.pk), 'month': '2026-11'})
            history = _client(self.viewer).get(reverse('weekly-off-assignments-history', kwargs={'employee_id': 'AUD0001'}))
        self.assertEqual(month.status_code, 403)
        self.assertEqual(history.status_code, 403)

    def test_an_unscoped_viewer_still_sees_the_employee(self):
        month = _client(self.viewer).get(reverse('hr-employee-month-calendar'), {'employee_id': str(self.employee.pk), 'month': '2026-11'})
        history = _client(self.viewer).get(reverse('weekly-off-assignments-history', kwargs={'employee_id': 'AUD0001'}))
        self.assertEqual(month.status_code, 200, month.data)
        self.assertEqual(history.status_code, 200, history.data)

    def test_history_for_an_unknown_employee_is_a_404_not_an_empty_success(self):
        response = _client(self.viewer).get(reverse('weekly-off-assignments-history', kwargs={'employee_id': 'NOPE'}))
        self.assertEqual(response.status_code, 404)


class EcrBranchScopeTests(TestCase):
    def setUp(self):
        self.branch = make_branch('AUD-HYD', 'Audit Hyderabad')
        self.other = make_branch('AUD-BLR', 'Audit Bengaluru')
        creator = make_user('audit_ecr_creator@test.com', role=make_role('audit_ecr_creator'))
        self.cycle = PayrollCycle.objects.create(
            cycle_start=datetime.date(2026, 3, 25), cycle_end=datetime.date(2026, 4, 24), pay_date=datetime.date(2026, 4, 30),
            created_by=creator, branch=self.branch, status='payslips_generated',
        )
        self.payroll_role = make_role('audit_ecr_payroll', permission_codenames=['payroll.view'])

    def _ask(self, user):
        _, failure = _get_authorized_cycle(SimpleNamespace(user=user), self.cycle.pk)
        return failure.status_code if failure is not None else None

    def test_a_payroll_user_with_no_branch_is_not_treated_as_a_global_admin(self):
        user = make_user('audit_ecr_nobranch@test.com', role=self.payroll_role)
        self.assertEqual(self._ask(user), 403)

    def test_a_payroll_user_of_another_branch_is_refused(self):
        user = make_user('audit_ecr_other@test.com', role=self.payroll_role, branch=self.other.branch_name)
        self.assertEqual(self._ask(user), 403)

    def test_a_payroll_user_of_the_same_branch_is_allowed(self):
        user = make_user('audit_ecr_same@test.com', role=self.payroll_role, branch=self.branch.branch_name)
        self.assertIsNone(self._ask(user))

    def test_a_settings_admin_may_download_any_branchs_cycle(self):
        admin = make_user('audit_ecr_admin@test.com', role=make_role('audit_ecr_admin', permission_codenames=['payroll.view', 'settings.edit']))
        self.assertIsNone(self._ask(admin))


class RecruitmentFixesTests(TestCase):
    def setUp(self):
        self.candidate = Candidate.objects.create(
            name='Audit Candidate', email='audit.candidate@test.com', position_applied='Engineer', status=Candidate.STATUS_SELECTED,
        )  # no branch

    def test_hr_decision_refuses_a_candidate_outside_the_callers_branch(self):
        user = make_user(
            'audit_hr_branch@test.com', branch='Some Other Branch',
            role=make_role('audit_hr_branch', permission_codenames=['recruitment.approve']),
        )
        response = _client(user).patch(reverse('candidate-hr-decision', kwargs={'pk': self.candidate.pk}), {'decision': 'reject'}, format='json')
        self.assertEqual(response.status_code, 403)
        self.candidate.refresh_from_db()
        self.assertFalse(self.candidate.hr_approved)

    def test_referral_rule_writes_need_settings_edit_not_just_settings_view(self):
        viewer = make_user('audit_ref_view@test.com', role=make_role('audit_ref_view', permission_codenames=['settings.view']))
        body = {'name': 'Audit rule', 'bonus_amount': '1000', 'min_months': 3}
        self.assertEqual(_client(viewer).post(reverse('referral-rule-list-create'), body, format='json').status_code, 403)
        self.assertEqual(_client(viewer).patch(reverse('referral-rule-detail', kwargs={'pk': 1}), body, format='json').status_code, 403)
        self.assertEqual(_client(viewer).delete(reverse('referral-rule-detail', kwargs={'pk': 1})).status_code, 403)

    def test_referral_rules_can_still_be_read_by_an_ordinary_user(self):
        # The referral page shows the rules to employees, so the list stays readable (that hunk was not ported).
        employee = make_user('audit_ref_emp@test.com', role=make_role('audit_ref_emp'))
        self.assertEqual(_client(employee).get(reverse('referral-rule-list-create')).status_code, 200)
