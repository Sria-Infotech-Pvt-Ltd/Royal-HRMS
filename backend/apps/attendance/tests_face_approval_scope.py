"""
Who may see, review and be notified about a Face ID registration (services_face_approval).

A reviewer needs facial_recognition.approve AND scope: the employee's assigned HR, else (no assigned HR who can approve)
anyone with the permission on the employee's branch; a superuser sees everything; nobody reviews their own request.
Rejecting needs a written reason, enforced by the API, not only by the screen.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, Placement, Position, PositionPermission
from apps.attendance.models import AttendanceFaceVerificationRules, AttendanceSettings, FaceRegistrationRequest
from apps.attendance.services_face_approval import notify_approvers_of_submission
from apps.notifications.models import Notification

APPROVE = ['facial_recognition.approve']


def _approver(email, *, branch='Kondapur', **extra):
    return make_user(email, role=make_role(f'role_{email}', permission_codenames=APPROVE), branch=branch, **extra)


def _request_for(employee) -> FaceRegistrationRequest:
    return FaceRegistrationRequest.objects.create(employee=employee, face_embedding=[0.1, 0.2, 0.3], liveness_passed=True, liveness_score=0.9)


def _as(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _ids(response) -> set[str]:
    return {row['id'] for row in response.data['data']['results']}


class _Scenario(TestCase):
    def setUp(self):
        cache.clear()
        self.assigned_hr = _approver('assigned-hr@test.com')
        self.branch_peer = _approver('branch-peer@test.com')
        self.other_branch = _approver('other-branch@test.com', branch='Madhapur')
        self.no_branch = _approver('no-branch@test.com', branch='')
        self.superuser = make_user('face-super@test.com', is_superuser=True)
        self.employee = make_user('face-employee@test.com', branch='Kondapur', employee_id='FE001', hr=self.assigned_hr)
        self.request = _request_for(self.employee)

    def pending(self, user):
        return _as(user).get(reverse('face-registration-pending'))

    def review(self, user, payload, pk=None):
        return _as(user).patch(reverse('face-registration-review', kwargs={'pk': pk or self.request.pk}), payload, format='json')


class AssignedHrScopeTests(_Scenario):
    def test_the_assigned_hr_sees_and_reviews_the_request(self):
        self.assertIn(str(self.request.pk), _ids(self.pending(self.assigned_hr)))
        response = self.review(self.assigned_hr, {'status': 'approved'})
        self.assertEqual(response.status_code, 200, response.data)
        self.request.refresh_from_db()
        self.assertEqual((self.request.status, self.request.approved_by_id), ('approved', self.assigned_hr.pk))

    def test_another_approver_on_the_same_branch_cannot_see_or_review_it_when_an_hr_is_assigned(self):
        self.assertNotIn(str(self.request.pk), _ids(self.pending(self.branch_peer)))
        self.assertEqual(self.review(self.branch_peer, {'status': 'approved'}).status_code, 404)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'pending')

    def test_assigned_to_me_narrows_the_queue_to_the_reviewers_own_employees(self):
        other = make_user('other-employee@test.com', branch='Kondapur', employee_id='FE002')   # no HR assigned
        other_request = _request_for(other)
        everything = _ids(self.pending(self.assigned_hr))
        mine = _ids(_as(self.assigned_hr).get(reverse('face-registration-pending'), {'assigned_to_me': '1'}))
        self.assertEqual(everything, {str(self.request.pk), str(other_request.pk)})   # in branch, other has no HR
        self.assertEqual(mine, {str(self.request.pk)})

    def test_an_assigned_hr_who_cannot_approve_does_not_strand_the_request(self):
        """Ambiguity decision: an assigned HR without the permission does not count as an assigned approver."""
        powerless_hr = make_user('powerless-hr@test.com', branch='Kondapur', role=make_role('powerless_role'))
        employee = make_user('stranded@test.com', branch='Kondapur', employee_id='FE003', hr=powerless_hr)
        stranded = _request_for(employee)
        self.assertIn(str(stranded.pk), _ids(self.pending(self.branch_peer)))
        self.assertEqual(self.review(self.branch_peer, {'status': 'approved'}, pk=stranded.pk).status_code, 200)


class BranchScopeTests(_Scenario):
    def setUp(self):
        super().setUp()
        self.unassigned = make_user('unassigned-employee@test.com', branch='Kondapur', employee_id='FE010')
        self.unassigned_request = _request_for(self.unassigned)

    def test_with_no_assigned_hr_an_approver_on_the_same_branch_sees_and_reviews_it(self):
        self.assertIn(str(self.unassigned_request.pk), _ids(self.pending(self.branch_peer)))
        self.assertEqual(self.review(self.branch_peer, {'status': 'approved'}, pk=self.unassigned_request.pk).status_code, 200)

    def test_an_approver_on_another_branch_cannot_see_or_review_it(self):
        self.assertNotIn(str(self.unassigned_request.pk), _ids(self.pending(self.other_branch)))
        self.assertEqual(self.review(self.other_branch, {'status': 'approved'}, pk=self.unassigned_request.pk).status_code, 404)
        self.unassigned_request.refresh_from_db()
        self.assertEqual(self.unassigned_request.status, 'pending')

    def test_an_approver_with_no_branch_sees_nothing_they_are_not_assigned(self):
        self.assertEqual(_ids(self.pending(self.no_branch)), set())
        self.assertEqual(self.review(self.no_branch, {'status': 'approved'}, pk=self.unassigned_request.pk).status_code, 404)


class AuthorizationTests(_Scenario):
    def test_someone_without_the_permission_can_neither_list_nor_review(self):
        nobody = make_user('nobody@test.com', branch='Kondapur', role=make_role('nobody_role'))
        self.assertEqual(self.pending(nobody).status_code, 403)
        self.assertEqual(self.review(nobody, {'status': 'approved'}).status_code, 403)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'pending')

    def test_the_employee_cannot_review_their_own_request_even_with_the_permission(self):
        approver_employee = _approver('self-approver@test.com')
        own = _request_for(approver_employee)
        response = self.review(approver_employee, {'status': 'approved'}, pk=own.pk)
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(str(own.pk), _ids(self.pending(approver_employee)))

    def test_not_even_a_superuser_can_review_their_own_request(self):
        own = _request_for(self.superuser)
        self.assertEqual(self.review(self.superuser, {'status': 'approved'}, pk=own.pk).status_code, 403)

    def test_a_superuser_still_sees_and_reviews_everything(self):
        self.assertIn(str(self.request.pk), _ids(self.pending(self.superuser)))
        self.assertEqual(self.review(self.superuser, {'status': 'approved'}).status_code, 200)

    def test_the_queue_exposes_the_employee_id_and_branch_but_never_the_face_vector(self):
        row = self.pending(self.assigned_hr).data['data']['results'][0]
        self.assertEqual((row['employee_code'], row['branch_name']), ('FE001', 'Kondapur'))
        self.assertNotIn('face_embedding', row)


class RejectionRemarksTests(_Scenario):
    def test_rejecting_without_remarks_is_refused_and_the_request_stays_pending(self):
        for payload in ({'status': 'rejected'}, {'status': 'rejected', 'notes': ''}, {'status': 'rejected', 'notes': '   '}):
            response = self.review(self.assigned_hr, payload)
            self.assertEqual(response.status_code, 400, payload)
            self.assertIn('reason', response.data['message'].lower())
        self.request.refresh_from_db()
        self.assertEqual((self.request.status, self.request.approved_by_id), ('pending', None))

    def test_rejecting_with_remarks_records_them(self):
        response = self.review(self.assigned_hr, {'status': 'rejected', 'notes': '  Photo too dark.  '})
        self.assertEqual(response.status_code, 200, response.data)
        self.request.refresh_from_db()
        self.assertEqual((self.request.status, self.request.notes), ('rejected', 'Photo too dark.'))

    def test_approving_needs_no_remarks(self):
        self.assertEqual(self.review(self.assigned_hr, {'status': 'approved'}).status_code, 200)


class SubmissionNotificationTests(_Scenario):
    def _notes(self, user):
        return Notification.objects.filter(user=user, notification_type='face_registration_pending')

    def test_only_the_assigned_hr_is_notified_and_only_once(self):
        self.assertEqual(notify_approvers_of_submission(self.request), 1)
        self.assertEqual(notify_approvers_of_submission(self.request), 0)       # no duplicate
        self.assertEqual(self._notes(self.assigned_hr).count(), 1)
        for other in (self.branch_peer, self.other_branch, self.no_branch, self.superuser, self.employee):
            self.assertEqual(self._notes(other).count(), 0, other.email)
        note = self._notes(self.assigned_hr).get()
        self.assertEqual((note.module, note.reference_id), ('facial_recognition', str(self.request.pk)))

    def test_with_no_hr_assigned_the_branch_approvers_are_notified(self):
        employee = make_user('no-hr@test.com', branch='Kondapur', employee_id='FE020')
        request = _request_for(employee)
        notify_approvers_of_submission(request)
        notified = set(Notification.objects.filter(notification_type='face_registration_pending', reference_id=str(request.pk))
                       .values_list('user__email', flat=True))
        self.assertEqual(notified, {'assigned-hr@test.com', 'branch-peer@test.com'})

    def test_when_nobody_on_the_branch_can_approve_a_superuser_is_told(self):
        employee = make_user('lonely@test.com', branch='Nowhere', employee_id='FE021')
        notify_approvers_of_submission(_request_for(employee))
        self.assertEqual(self._notes(self.superuser).count(), 1)

    def test_submitting_through_the_api_notifies_the_assigned_hr(self):
        settings, _ = AttendanceSettings.objects.get_or_create(is_active=True)
        AttendanceFaceVerificationRules.objects.update_or_create(settings=settings, defaults={'is_mandatory': True})
        FaceRegistrationRequest.objects.all().delete()
        response = _as(self.employee).post(reverse('face-registration-submit'), {
            'face_embedding': [0.1, 0.2, 0.3, 0.4], 'liveness_passed': True, 'liveness_score': 0.95, 'consent_acknowledged': True,
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self._notes(self.assigned_hr).count(), 1)


class SeatPermissionUpdateTests(TestCase):
    """Granting the approval permission to an existing seat keeps what the seat already has (the UAT change for Samreen)."""

    def test_adding_one_permission_keeps_the_existing_ones_and_is_audited(self):
        cache.clear()
        admin = make_user('seat-admin@test.com', is_superuser=True)
        holder = make_user('seat-holder@test.com', role=make_role('hr_ops', permission_codenames=[
            'leave.approve', 'employees.view', 'employees.edit', 'recruitment.view', 'recruitment.edit', 'onboarding.approve']))
        seat = Position.objects.get(pk=Placement.objects.filter(employee=holder).values_list('position_id', flat=True).get())
        before = set(PositionPermission.objects.filter(position=seat).values_list('permission__codename', flat=True))
        self.assertEqual(len(before), 6)

        response = _as(admin).put(reverse('position-permissions', args=[seat.pk]), {'codenames': sorted(before | {'facial_recognition.approve'})}, format='json')
        self.assertEqual(response.status_code, 200, response.data)

        after = set(PositionPermission.objects.filter(position=seat).values_list('permission__codename', flat=True))
        self.assertEqual(after, before | {'facial_recognition.approve'})
        audit = AuditLog.objects.filter(action='position_permissions_update', object_id=str(seat.pk)).get()
        self.assertEqual(set(audit.changes['after']['codenames']) - set(audit.changes['before']['codenames']), {'facial_recognition.approve'})
