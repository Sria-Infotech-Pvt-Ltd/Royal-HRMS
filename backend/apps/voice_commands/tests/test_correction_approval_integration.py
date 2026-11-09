"""
Voice approve/reject of attendance corrections against Aira's REAL correction views, users and permission model
(private test DB only) - nothing about production's import paths or data shapes is assumed.

Includes the case production's first-page-only lookup got wrong: the target correction sits beyond the first page of the
reviewer's queue (110 newer requests ahead of it, page size 100) and must still be found by name.
"""
from __future__ import annotations

import datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from apps.accounts.factories import make_role, make_user
from apps.attendance.models import AttendanceCorrection
from apps.voice_commands import language
from apps.voice_commands.executor import (
    INTENT_APPROVE_ATTENDANCE_CORRECTION, INTENT_REJECT_ATTENDANCE_CORRECTION, execute_intent,
)
from apps.voice_commands.executor_correction_approval import (
    execute_confirm_attendance_correction_approval, execute_identify_attendance_correction_approval_target,
)

_FILLER_COUNT = 110


def _request(user):
    return SimpleNamespace(user=user, META={})


class CorrectionApprovalIntegrationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.addCleanup(language.set_current_language, language.LANG_EN)
        language.set_current_language(language.LANG_EN)
        reviewer_perms = ['attendance.view', 'attendance.create']
        self.manager = make_user(
            'vc-mgr@test.com', role=make_role('vc_manager', permission_codenames=reviewer_perms, can_manage_team=True),
        )
        self.hr = make_user('vc-hr@test.com', role=make_role('vc_hr', permission_codenames=reviewer_perms))
        self.outsider = make_user('vc-out@test.com', role=make_role('vc_outsider', permission_codenames=reviewer_perms))
        self.plain = make_user('vc-plain@test.com', role=make_role('vc_plain', permission_codenames=['attendance.view']))
        self.target = make_user('vc-target@test.com', role=make_role('vc_target_emp'), full_name='Zelda Quartz',
            onboarding_status='complete',
        )
        self.filler = make_user('vc-filler@test.com', role=make_role('vc_filler_emp'), full_name='Filler Person',
            onboarding_status='complete',
        )

    def _correction(self, employee, day_offset, *, status=AttendanceCorrection.STATUS_PENDING, with_hr=False):
        return AttendanceCorrection(
            employee=employee, date=datetime.date.today() - datetime.timedelta(days=day_offset),
            punch_type=AttendanceCorrection.PUNCH_IN, requested_in_time=datetime.time(9, 0),
            reason='forgot_to_punch', status=status, created_by=employee,
            l1_approver=self.manager, l2_approver=self.hr if with_hr else None,
        )

    def _target_correction(self, **kwargs):
        correction = self._correction(self.target, 1, **kwargs)
        correction.save()
        return correction

    def test_target_beyond_the_first_page_is_found(self):
        target = self._target_correction()  # created first => oldest => LAST in the newest-first queue
        AttendanceCorrection.objects.bulk_create([
            self._correction(self.filler, 2 + index) for index in range(_FILLER_COUNT)
        ])
        result = execute_identify_attendance_correction_approval_target(_request(self.manager), 'approve', 'zelda')
        self.assertTrue(result.success, result.message)
        self.assertEqual(result.data['outcome'], 'single_match')
        self.assertEqual(result.data['matched']['correction_id'], str(target.pk))
        self.assertIn('Zelda Quartz', result.message)
        self.assertIn('approve this request', result.message)

    def test_unknown_name_is_zero_match(self):
        self._target_correction()
        result = execute_identify_attendance_correction_approval_target(_request(self.manager), 'approve', 'nobody')
        self.assertFalse(result.success)
        self.assertEqual(result.data['outcome'], 'zero_match')

    def test_no_name_asks_who(self):
        result = execute_identify_attendance_correction_approval_target(_request(self.manager), 'reject', None)
        self.assertEqual(result.data['outcome'], 'need_name')
        self.assertIn('Whose attendance correction would you like to reject?', result.message)

    def test_reviewer_who_is_not_the_designated_approver_sees_nothing(self):
        self._target_correction()
        result = execute_identify_attendance_correction_approval_target(_request(self.outsider), 'approve', 'zelda')
        self.assertEqual(result.data['outcome'], 'zero_match')

    def test_confirm_approve_is_final_when_no_hr_stage_is_configured(self):
        correction = self._target_correction()
        result = execute_confirm_attendance_correction_approval(_request(self.manager), 'approve', str(correction.pk))
        self.assertTrue(result.success, result.message)
        self.assertEqual(result.message, "Zelda Quartz's attendance correction has been approved.")
        correction.refresh_from_db()
        self.assertEqual(correction.status, AttendanceCorrection.STATUS_APPROVED)

    def test_confirm_approve_with_hr_stage_says_it_was_sent_to_hr(self):
        correction = self._target_correction(with_hr=True)
        result = execute_confirm_attendance_correction_approval(_request(self.manager), 'approve', str(correction.pk))
        self.assertTrue(result.success, result.message)
        self.assertIn('sent to HR for final review', result.message)
        correction.refresh_from_db()
        self.assertEqual(correction.status, AttendanceCorrection.STATUS_L2_PENDING)

    def test_a_manager_whose_stage_has_passed_is_not_offered_the_request(self):
        self._target_correction(status=AttendanceCorrection.STATUS_L2_PENDING, with_hr=True)
        result = execute_identify_attendance_correction_approval_target(_request(self.manager), 'approve', 'zelda')
        self.assertEqual(result.data['outcome'], 'zero_match')
        hr_result = execute_identify_attendance_correction_approval_target(_request(self.hr), 'approve', 'zelda')
        self.assertEqual(hr_result.data['outcome'], 'single_match')

    def test_confirm_reject(self):
        correction = self._target_correction()
        result = execute_confirm_attendance_correction_approval(_request(self.manager), 'reject', str(correction.pk))
        self.assertTrue(result.success, result.message)
        self.assertEqual(result.message, "Zelda Quartz's attendance correction has been rejected.")
        correction.refresh_from_db()
        self.assertEqual(correction.status, AttendanceCorrection.STATUS_REJECTED)

    def test_confirm_surfaces_the_real_view_rejection_when_eligibility_changed(self):
        correction = self._target_correction()
        # Someone else already actioned it between the identify and confirm turns.
        AttendanceCorrection.objects.filter(pk=correction.pk).update(status=AttendanceCorrection.STATUS_REJECTED)
        result = execute_confirm_attendance_correction_approval(_request(self.manager), 'approve', str(correction.pk))
        self.assertFalse(result.success)
        self.assertNotIn('has been approved', result.message)

    def test_confirm_without_an_id_asks_to_start_over(self):
        result = execute_confirm_attendance_correction_approval(_request(self.manager), 'approve', None)
        self.assertFalse(result.success)
        self.assertIn('start over', result.message)

    def test_hindi_confirmation_prompt(self):
        self._target_correction()
        language.set_current_language(language.LANG_HI)
        result = execute_identify_attendance_correction_approval_target(_request(self.manager), 'approve', 'zelda')
        self.assertIn('पंच-इन', result.message)
        self.assertIn('स्वीकृत', result.message)

    def test_voice_gate_blocks_a_caller_without_attendance_create(self):
        self._target_correction()
        for intent in (INTENT_APPROVE_ATTENDANCE_CORRECTION, INTENT_REJECT_ATTENDANCE_CORRECTION):
            with self.subTest(intent):
                result = execute_intent(intent, _request(self.plain), slots={'stage': 'identify', 'name_query': 'zelda'})
                self.assertFalse(result.success)
                self.assertEqual(result.message, "You don't have permission to do that.")

    def test_execute_intent_routes_identify_and_confirm_for_a_permitted_caller(self):
        correction = self._target_correction()
        identify = execute_intent(
            INTENT_REJECT_ATTENDANCE_CORRECTION, _request(self.manager), slots={'stage': 'identify', 'name_query': 'zelda'},
        )
        self.assertEqual(identify.data['outcome'], 'single_match')
        confirm = execute_intent(
            INTENT_REJECT_ATTENDANCE_CORRECTION, _request(self.manager),
            slots={'stage': 'confirm', 'correction_id': identify.data['matched']['correction_id']},
        )
        self.assertTrue(confirm.success, confirm.message)
        correction.refresh_from_db()
        self.assertEqual(correction.status, AttendanceCorrection.STATUS_REJECTED)


class QueuePagingBoundsTests(SimpleTestCase):
    """The page loop is bounded and never reports success on a failed page (view mocked, no data needed)."""

    @staticmethod
    def _response(rows, total_pages, status=200):
        from unittest.mock import MagicMock
        return MagicMock(
            status_code=status,
            data={'data': {'count': len(rows), 'total_pages': total_pages, 'results': rows}, 'message': 'boom'},
        )

    def _identify(self, side_effect):
        with patch('apps.voice_commands.executor_correction_approval.force_authenticate'), \
             patch('apps.voice_commands.executor_correction_approval.HRCorrectionListView') as mock_view:
            mock_view.as_view.return_value.side_effect = side_effect
            result = execute_identify_attendance_correction_approval_target(_request(SimpleNamespace()), 'approve', 'ravi')
        return result, mock_view.as_view.return_value

    def test_reads_every_page_and_requests_page_size_100(self):
        page_1 = self._response([{'id': 'a', 'name': 'Other', 'date': '2026-01-01', 'punch_type': 'IN', 'can_action': True}], 2)
        page_2 = self._response([{'id': 'b', 'name': 'Ravi Teja', 'date': '2026-01-02', 'punch_type': 'OUT', 'can_action': True}], 2)
        result, view = self._identify([page_1, page_2])
        self.assertEqual(result.data['outcome'], 'single_match')
        self.assertEqual(result.data['matched']['correction_id'], 'b')
        requested = [call.args[0].GET for call in view.call_args_list]
        self.assertEqual([params['page'] for params in requested], ['1', '2'])
        self.assertTrue(all(params['page_size'] == '100' for params in requested))

    def test_a_failing_later_page_is_a_failure_not_a_partial_success(self):
        page_1 = self._response([], 2)
        page_2 = self._response([], 2, status=500)
        result, _ = self._identify([page_1, page_2])
        self.assertFalse(result.success)
        self.assertIsNone(result.data)

    def test_the_page_loop_is_bounded(self):
        empty = self._response([], 100000)
        result, view = self._identify(lambda *_: empty)
        self.assertEqual(view.call_count, 50)
        self.assertEqual(result.data['outcome'], 'zero_match')
