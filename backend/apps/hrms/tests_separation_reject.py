"""UAT-018: rejecting a separation needs a reason at every stage, keeps the record, and reference numbers are never reused."""
import datetime

from django.core.cache import cache
from django.db import transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.hrms.models import (
    APPROVAL_PENDING, SEP_PENDING, SEP_REJECTED, SEP_STAGE_MANAGER, SeparationApprovalStage, SeparationRequest,
    SeparationRequestNumberSequence,
)

TODAY = datetime.date.today()


def _request(employee, number):
    return SeparationRequest.objects.create(
        employee=employee, separation_type='resignation', request_date=TODAY,
        proposed_last_working_day=TODAY + datetime.timedelta(days=30), request_number=number, status=SEP_PENDING,
    )


class SeparationRejectTests(TestCase):
    def setUp(self):
        cache.clear()
        self.employee = make_user('leaver@test.com', employee_id='EMPSR001', branch='Kondapur')
        self.approver = make_user(
            'approver@test.com', employee_id='EMPSR002', branch='Kondapur',
            role=make_role('sep_approver_test', permission_codenames=['separation.approve', 'separation.view']),
        )
        self.request_row = _request(self.employee, 1)
        self.stage = SeparationApprovalStage.objects.create(
            request=self.request_row, stage=SEP_STAGE_MANAGER, sequence=1, approver=self.approver, status=APPROVAL_PENDING,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.approver)
        self.url = reverse('separation-stage-action', args=[self.request_row.id, self.stage.id])

    def test_rejecting_without_a_reason_is_refused(self):
        for remarks in ('', '   ', None):
            response = self.client.post(self.url, {'action': 'reject', 'remarks': remarks}, format='json')
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()['data']['remarks'], 'A reason is required.')
        self.request_row.refresh_from_db()
        self.assertEqual(self.request_row.status, SEP_PENDING)

    def test_rejecting_with_a_reason_keeps_the_record_and_stores_the_reason(self):
        response = self.client.post(self.url, {'action': 'reject', 'remarks': 'Notice period not served.'}, format='json')
        self.assertEqual(response.status_code, 200, response.json())
        self.request_row.refresh_from_db()
        self.stage.refresh_from_db()
        self.assertEqual(self.request_row.status, SEP_REJECTED)  # the row still exists
        self.assertEqual(self.stage.remarks, 'Notice period not served.')

    def test_approving_needs_no_reason(self):
        response = self.client.post(self.url, {'action': 'approve'}, format='json')
        self.assertEqual(response.status_code, 200, response.json())


class SeparationNumberingTests(TestCase):
    def test_numbers_are_never_reused_even_after_the_newest_row_is_deleted(self):
        with transaction.atomic():
            first = SeparationRequestNumberSequence.next_number()
        with transaction.atomic():
            second = SeparationRequestNumberSequence.next_number()
        self.assertEqual(second, first + 1)
        employee = make_user('numbering@test.com', employee_id='EMPSN001')
        row = _request(employee, second)
        row.delete()  # the newest request is gone...
        with transaction.atomic():
            third = SeparationRequestNumberSequence.next_number()
        self.assertEqual(third, second + 1)  # ...and its number is still not handed out again


class StaleSeparationTests(TestCase):
    """UAT-064: a request still pending after its last working day is flagged (never auto-closed)."""

    def _stale(self, status=SEP_PENDING, days_ago=5, number=10):
        employee = make_user(f'stale{number}@test.com', employee_id=f'EMPST{number:03d}')
        return SeparationRequest.objects.create(
            employee=employee, separation_type='retirement', request_date=TODAY - datetime.timedelta(days=60),
            proposed_last_working_day=TODAY - datetime.timedelta(days=days_ago), request_number=number, status=status,
        )

    def test_flag_is_true_only_for_pending_requests_past_their_last_day(self):
        from apps.hrms.serializers import SeparationRequestSerializer
        self.assertTrue(SeparationRequestSerializer(self._stale(number=11)).data['is_stale'])
        self.assertFalse(SeparationRequestSerializer(self._stale(status=SEP_REJECTED, number=12)).data['is_stale'])
        future = self._stale(days_ago=-10, number=13)
        self.assertFalse(SeparationRequestSerializer(future).data['is_stale'])

    def test_report_command_lists_them_and_changes_nothing(self):
        from io import StringIO
        from django.core.management import call_command
        row = self._stale(number=14)
        out = StringIO()
        call_command('report_stale_separations', stdout=out)
        self.assertIn('SEP-14', out.getvalue())
        self.assertIn('Nothing was changed', out.getvalue())
        row.refresh_from_db()
        self.assertEqual(row.status, SEP_PENDING)


class SegregationOfDutiesTests(TestCase):
    """UAT-044: the person who raised a separation cannot approve, clear or finalise it; every step produces an activity entry."""

    def setUp(self):
        cache.clear()
        from apps.hrms.models import SEP_CLEARANCE_IT, SeparationClearance
        self.employee = make_user('sod.leaver@test.com', employee_id='EMPSD001', branch='Kondapur')
        self.admin = make_user(
            'sod.admin@test.com', employee_id='EMPSD002', branch='Kondapur',
            role=make_role('sod_admin_test', permission_codenames=['separation.approve', 'separation.view']),
        )
        self.other = make_user(
            'sod.other@test.com', employee_id='EMPSD003', branch='Kondapur',
            role=make_role('sod_other_test', permission_codenames=['separation.approve', 'separation.view']),
        )
        self.request_row = _request(self.employee, 40)
        self.request_row.created_by = self.admin  # the admin raised it
        self.request_row.save(update_fields=['created_by'])
        self.stage = SeparationApprovalStage.objects.create(
            request=self.request_row, stage=SEP_STAGE_MANAGER, sequence=1, approver=None, status=APPROVAL_PENDING,
        )
        self.clearance = SeparationClearance.objects.create(request=self.request_row, clearance_type=SEP_CLEARANCE_IT)
        self.stage_url = reverse('separation-stage-action', args=[self.request_row.id, self.stage.id])
        self.clearance_url = reverse('separation-clearance-action', args=[self.request_row.id, self.clearance.id])
        self.client = APIClient()

    def test_the_requester_cannot_approve_a_stage_or_clear_it(self):
        self.client.force_authenticate(user=self.admin)
        for url in (self.stage_url, self.clearance_url):
            response = self.client.post(url, {'action': 'approve'}, format='json')
            self.assertEqual(response.status_code, 403, url)
            self.assertIn('You submitted this separation request', response.json()['message'])
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.status, APPROVAL_PENDING)  # nothing changed

    def test_someone_else_can_and_every_step_leaves_an_activity_entry(self):
        from apps.hrms.models import SeparationActivity
        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.client.post(self.stage_url, {'action': 'approve', 'remarks': 'ok'}, format='json').status_code, 200)
        self.assertEqual(self.client.post(self.clearance_url, {'action': 'approve'}, format='json').status_code, 200)
        messages = list(SeparationActivity.objects.filter(request=self.request_row).values_list('message', flat=True))
        self.assertEqual(len(messages), 2)
        self.assertTrue(any('Manager' in message and 'approved' in message for message in messages))
        self.assertTrue(any('IT' in message and 'approved' in message for message in messages))

    def test_the_documented_override_allows_the_step_and_audits_it(self):
        from django.test import override_settings
        from apps.accounts.models import AuditLog
        self.client.force_authenticate(user=self.admin)
        with override_settings(SEPARATION_ALLOW_REQUESTER_APPROVAL=True):
            response = self.client.post(self.stage_url, {'action': 'approve'}, format='json')
        self.assertEqual(response.status_code, 200, response.json())
        event = AuditLog.objects.get(action='separation_self_approval_override')
        self.assertEqual((event.user_id, event.changes['step']), (self.admin.id, SEP_STAGE_MANAGER))

    def test_the_override_is_off_by_default(self):
        from django.conf import settings
        self.assertFalse(settings.SEPARATION_ALLOW_REQUESTER_APPROVAL)
