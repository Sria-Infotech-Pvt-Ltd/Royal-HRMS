"""Review (approve / reject) flow for attendance correction requests: stage-gated
permissions, L1 -> L2 routing, final-approval side effects, and the review queue scope."""
from __future__ import annotations

import datetime

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.attendance.models import AttendanceCorrection, AttendancePunch


class CorrectionReviewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        reviewer_role = make_role('correction_reviewer', permission_codenames=['attendance.view', 'attendance.create'])
        self.employee = make_user('corr-emp@test.com', role=make_role('corr_employee'))
        manager_role = make_role('correction_manager', permission_codenames=['attendance.view', 'attendance.create'], can_manage_team=True)
        self.manager = make_user('corr-mgr@test.com', role=manager_role)
        self.hr = make_user('corr-hr@test.com', role=reviewer_role)
        self.outsider = make_user('corr-out@test.com', role=reviewer_role)
        self.plain = make_user('corr-plain@test.com', role=make_role('corr_plain', permission_codenames=['attendance.view']))

    def _correction(self, status=AttendanceCorrection.STATUS_PENDING, with_hr=True):
        return AttendanceCorrection.objects.create(
            employee=self.employee, date=datetime.date.today() - datetime.timedelta(days=1),
            punch_type=AttendanceCorrection.PUNCH_BOTH,
            requested_in_time=datetime.time(9, 0), requested_out_time=datetime.time(18, 0),
            reason='forgot_to_punch', status=status, created_by=self.employee,
            l1_approver=self.manager, l2_approver=self.hr if with_hr else None,
        )

    def _review(self, user, correction, action='approve'):
        self.client.force_authenticate(user=user)
        return self.client.patch(
            reverse('hr-correction-review', args=[correction.pk]), {'action': action}, format='json',
        )

    def test_l1_approval_with_hr_configured_moves_to_hr_without_punches(self):
        correction = self._correction()
        resp = self._review(self.manager, correction)
        self.assertEqual(resp.status_code, 200, resp.data)
        correction.refresh_from_db()
        self.assertEqual(correction.status, AttendanceCorrection.STATUS_L2_PENDING)
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

    def test_final_approval_creates_both_punches(self):
        correction = self._correction(status=AttendanceCorrection.STATUS_L2_PENDING)
        resp = self._review(self.hr, correction)
        self.assertEqual(resp.status_code, 200, resp.data)
        correction.refresh_from_db()
        self.assertEqual(correction.status, AttendanceCorrection.STATUS_APPROVED)
        self.assertEqual(AttendancePunch.objects.filter(employee=self.employee).count(), 2)

    def test_l1_approval_without_hr_is_final(self):
        correction = self._correction(with_hr=False)
        resp = self._review(self.manager, correction)
        self.assertEqual(resp.status_code, 200, resp.data)
        correction.refresh_from_db()
        self.assertEqual(correction.status, AttendanceCorrection.STATUS_APPROVED)

    def test_reject_creates_no_punches(self):
        correction = self._correction()
        resp = self._review(self.manager, correction, action='reject')
        self.assertEqual(resp.status_code, 200, resp.data)
        correction.refresh_from_db()
        self.assertEqual(correction.status, AttendanceCorrection.STATUS_REJECTED)
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

    def test_wrong_stage_approver_is_forbidden(self):
        correction = self._correction()  # waiting on the manager (L1)
        self.assertEqual(self._review(self.hr, correction).status_code, 403)
        self.assertEqual(self._review(self.outsider, correction).status_code, 403)
        correction.refresh_from_db()
        self.assertEqual(correction.status, AttendanceCorrection.STATUS_PENDING)

    def test_user_without_attendance_create_is_forbidden(self):
        correction = self._correction()
        self.assertEqual(self._review(self.plain, correction).status_code, 403)

    def test_already_reviewed_request_cannot_be_reviewed_again(self):
        correction = self._correction(status=AttendanceCorrection.STATUS_REJECTED)
        self.assertEqual(self._review(self.manager, correction).status_code, 404)

    def test_invalid_action_rejected(self):
        correction = self._correction()
        self.assertEqual(self._review(self.manager, correction, action='maybe').status_code, 400)

    def test_queue_is_scoped_to_the_designated_approver(self):
        self._correction()
        self.client.force_authenticate(user=self.manager)
        mine = self.client.get(reverse('hr-corrections-list'), {'status': 'pending'})
        self.assertEqual(mine.status_code, 200, mine.data)
        self.assertEqual(mine.data['data']['count'], 1)

        self.client.force_authenticate(user=self.outsider)
        theirs = self.client.get(reverse('hr-corrections-list'), {'status': 'pending'})
        self.assertEqual(theirs.data['data']['count'], 0)
