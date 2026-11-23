"""
Tests for face verification at punch time (PunchService.record_punch calling
FaceVerificationService) and the employee's own status endpoint.

Split out of tests_face_registration.py (that file covers the enrollment/
approval workflow only) — see services_face_matching.py for the service
under test here.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.attendance.models import (
    AttendanceFaceVerificationRules,
    AttendancePunch,
    AttendanceSettings,
    FaceRegistrationRequest,
)
from config.test_runner import TEST_COMPANY_CODE


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(
        reverse('login'),
        {'company_code': TEST_COMPANY_CODE, 'email': email, 'password': password},
        format='json',
    )
    assert resp.status_code == 200, resp.data
    return resp


def _set_face_verification_mandatory(is_mandatory: bool) -> None:
    """Flips the org-wide toggle (Attendance Settings -> Face ID Verification)
    that FaceVerificationService.verify_for_punch and the HR register endpoint
    now gate on."""
    settings, _ = AttendanceSettings.objects.get_or_create(is_active=True)
    AttendanceFaceVerificationRules.objects.update_or_create(
        settings=settings, defaults={'is_mandatory': is_mandatory},
    )


# A 128-length vector (matching a real face-api.js descriptor's dimension),
# and a second vector far enough away to fail the FACE_MATCH_MAX_DISTANCE
# threshold — used to test both the match and mismatch paths.
REGISTERED_EMBEDDING = [0.01 * i for i in range(128)]
MATCHING_EMBEDDING   = [v + 0.001 for v in REGISTERED_EMBEDDING]   # tiny distance, well under 0.6
MISMATCHED_EMBEDDING = [v + 1.0 for v in REGISTERED_EMBEDDING]     # euclidean distance ~11.3, well over 0.6
# Both land inside the low-confidence band (distance within
# FACE_MATCH_LOW_CONFIDENCE_MARGIN of FACE_MATCH_MAX_DISTANCE=0.6) but are
# distinct vectors — a different embedding_fingerprint each, so submitting
# both in sequence exercises the step-up corroboration path without ever
# tripping anti-replay (that check only fires on a byte-identical embedding).
BORDERLINE_EMBEDDING_A = [v + 0.0503 for v in REGISTERED_EMBEDDING]  # distance ~0.569
BORDERLINE_EMBEDDING_B = [v + 0.0507 for v in REGISTERED_EMBEDDING]  # distance ~0.574


def _make_approved_request(employee) -> FaceRegistrationRequest:
    return FaceRegistrationRequest.objects.create(
        employee=employee,
        face_embedding=REGISTERED_EMBEDDING,
        liveness_passed=True,
        liveness_score=0.9,
        status=FaceRegistrationRequest.STATUS_APPROVED,
        is_active=True,
    )


class FaceVerificationPunchTests(TestCase):
    """
    Default (no explicit _set_face_verification_mandatory call): the org-wide
    toggle is unconfigured, which is_face_verification_mandatory() treats as
    off — matching the pre-toggle behaviour these "unaffected" tests exercise.
    Tests that verify the mandatory-enforcement path turn the toggle on
    explicitly, since that's now a precondition, not the default.
    """

    def setUp(self):
        cache.clear()
        self.client   = APIClient()
        role          = make_role('employee')
        self.employee = make_user('faceverify@test.com', role=role, password='TestPass123!')
        _login(self.client, 'faceverify@test.com')

    def tearDown(self):
        # Several tests here call _set_face_verification_mandatory(True),
        # which caches a real AttendanceSettings row — the DB write rolls
        # back with the test transaction, but the cache entry doesn't, so
        # without this it leaks a stale is_mandatory=True into whichever
        # test (in this file or, worse, an entirely unrelated module in the
        # same test run) reads AttendanceSettingsCacheService next.
        cache.clear()

    def _punch(self, **overrides):
        payload = {'punch_type': 'IN', 'attendance_mode': 'wfh'}
        payload.update(overrides)
        return self.client.post(reverse('attendance-punch'), payload, format='json')

    def test_punch_without_registration_is_unaffected(self):
        resp = self._punch()
        self.assertEqual(resp.status_code, 200, resp.data)
        punch = AttendancePunch.objects.get(employee=self.employee)
        self.assertFalse(punch.face_verified)
        self.assertIsNone(punch.face_match_distance)

    def test_no_registration_is_rejected_when_mandatory(self):
        # Toggle on, no registration at all — the whole point of "mandatory":
        # you must register before you can punch, not just skip verification.
        _set_face_verification_mandatory(True)
        resp = self._punch()
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('mandatory', resp.data['message'].lower())
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

    def test_approved_registration_without_embedding_is_rejected(self):
        _set_face_verification_mandatory(True)
        _make_approved_request(self.employee)
        resp = self._punch()
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('face verification is required', resp.data['message'].lower())
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

    def test_approved_registration_with_matching_embedding_succeeds(self):
        _set_face_verification_mandatory(True)
        _make_approved_request(self.employee)
        resp = self._punch(face_embedding=MATCHING_EMBEDDING)
        self.assertEqual(resp.status_code, 200, resp.data)
        punch = AttendancePunch.objects.get(employee=self.employee)
        self.assertTrue(punch.face_verified)
        self.assertIsNotNone(punch.face_match_distance)
        self.assertLess(punch.face_match_distance, 0.6)

    def test_approved_registration_with_mismatched_embedding_is_rejected(self):
        _set_face_verification_mandatory(True)
        _make_approved_request(self.employee)
        resp = self._punch(face_embedding=MISMATCHED_EMBEDDING)
        self.assertEqual(resp.status_code, 403, resp.data)
        # FR-2: a clean mismatch message, not the old lighting-flavored
        # wording — see services_face_matching.py's _EMBEDDING_MISMATCH_MESSAGE.
        self.assertIn("couldn't match your face", resp.data['message'].lower())
        self.assertNotIn('lighting', resp.data['message'].lower())
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

    def test_pending_registration_does_not_require_verification_when_toggle_off(self):
        # Only an APPROVED request gates the punch — pending/rejected don't —
        # and here the org toggle is off anyway, so nobody is gated regardless.
        FaceRegistrationRequest.objects.create(
            employee=self.employee, face_embedding=REGISTERED_EMBEDDING, liveness_passed=True,
        )
        resp = self._punch()
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_pending_registration_is_rejected_when_mandatory(self):
        # Toggle on: a pending (not yet approved) request doesn't satisfy
        # "mandatory" — same as having no registration at all.
        _set_face_verification_mandatory(True)
        FaceRegistrationRequest.objects.create(
            employee=self.employee, face_embedding=REGISTERED_EMBEDDING, liveness_passed=True,
        )
        resp = self._punch()
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('mandatory', resp.data['message'].lower())

    def test_voice_source_is_gated_the_same_as_web_when_mandatory(self):
        # Voice runs through the same browser tab as web (see AttendancePunch's
        # own docstring) — the voice-initiated clock-in conversation opens the
        # camera for its own "taking facial proof" turn (see apps.voice_commands.
        # conversation_clock_in_face) before ever reaching this endpoint with an
        # embedding attached, same as web. No embedding yet -> same rejection.
        _set_face_verification_mandatory(True)
        _make_approved_request(self.employee)
        resp = self._punch(source='voice')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('face verification is required', resp.data['message'].lower())
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

    def test_voice_source_with_matching_embedding_succeeds(self):
        _set_face_verification_mandatory(True)
        _make_approved_request(self.employee)
        resp = self._punch(source='voice', face_embedding=MATCHING_EMBEDDING)
        self.assertEqual(resp.status_code, 200, resp.data)
        punch = AttendancePunch.objects.get(employee=self.employee)
        self.assertTrue(punch.face_verified)

    def test_toggle_off_skips_verification_even_with_approved_registration(self):
        # The org toggle is the single source of truth: off means nobody is
        # asked to verify, even an employee approved while it was previously on.
        _set_face_verification_mandatory(False)
        _make_approved_request(self.employee)
        resp = self._punch()
        self.assertEqual(resp.status_code, 200, resp.data)
        punch = AttendancePunch.objects.get(employee=self.employee)
        self.assertFalse(punch.face_verified)


class FaceVerificationLowConfidenceFailClosedTests(TestCase):
    """A borderline-distance match (within FACE_MATCH_LOW_CONFIDENCE_MARGIN of
    FACE_MATCH_MAX_DISTANCE) is rejected outright, every time, with no way to
    turn it into an accept by retrying — see FACE_MATCH_LOW_CONFIDENCE_MARGIN's
    own docstring in services_face_matching.py for why an earlier version that
    accepted on a second corroborating capture didn't hold up against a real
    retest: the same impostor reproduced a borderline distance on 4 of 5
    captures, so a second draw barely changed the odds."""

    def setUp(self):
        cache.clear()
        self.client   = APIClient()
        role          = make_role('employee_low_conf')
        self.employee = make_user('lowconf@test.com', role=role, password='TestPass123!')
        _login(self.client, 'lowconf@test.com')
        _set_face_verification_mandatory(True)
        _make_approved_request(self.employee)

    def tearDown(self):
        cache.clear()

    def _punch(self, **overrides):
        payload = {'punch_type': 'IN', 'attendance_mode': 'wfh'}
        payload.update(overrides)
        return self.client.post(reverse('attendance-punch'), payload, format='json')

    def test_borderline_capture_is_rejected(self):
        resp = self._punch(face_embedding=BORDERLINE_EMBEDDING_A, capture_session_id='session-a')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

        from apps.attendance.models import FaceVerificationAttempt
        attempt = FaceVerificationAttempt.objects.get(employee=self.employee)
        # is_match=False on the row itself — this is a genuine rejection now,
        # not a "pending" match, so it counts toward the failed-attempt cap
        # like any other mismatch.
        self.assertFalse(attempt.is_match)
        self.assertEqual(attempt.rejection_reason, FaceVerificationAttempt.REJECTION_LOW_CONFIDENCE_PENDING)

    def test_second_independent_borderline_capture_is_also_rejected(self):
        # A second, different-session borderline capture used to corroborate
        # the first into an accept — it no longer does. Both are rejected.
        first = self._punch(face_embedding=BORDERLINE_EMBEDDING_A, capture_session_id='session-a')
        self.assertEqual(first.status_code, 403, first.data)

        second = self._punch(face_embedding=BORDERLINE_EMBEDDING_B, capture_session_id='session-b')
        self.assertEqual(second.status_code, 403, second.data)
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

    def test_confident_match_is_unaffected(self):
        resp = self._punch(face_embedding=MATCHING_EMBEDDING, capture_session_id='session-a')
        self.assertEqual(resp.status_code, 200, resp.data)


class FaceVerificationSourceBypassTests(TestCase):
    """The client-supplied `source` must not decide whether face verification
    runs: an employee could previously send source='manual' or 'biometric' and
    punch with no face check at all. Face ID is mandatory and the employee
    has an approved registration throughout."""

    def setUp(self):
        cache.clear()
        self.client   = APIClient()
        self.employee = make_user('facebypass@test.com', role=make_role('employee_bypass'),
                                  password='TestPass123!', employee_id='FBP1')
        _login(self.client, 'facebypass@test.com')
        _set_face_verification_mandatory(True)
        _make_approved_request(self.employee)

    def tearDown(self):
        cache.clear()

    def _punch(self, punch_type='IN', **overrides):
        # 'office', not 'wfh': a WFH punch now needs an approved WFH request
        # first, which would refuse the punch before face verification runs.
        payload = {'punch_type': punch_type, 'attendance_mode': 'office'}
        payload.update(overrides)
        return self.client.post(reverse('attendance-punch'), payload, format='json')

    def _assert_no_punch(self):
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

    def test_manual_source_is_refused_for_clock_in_and_out(self):
        for punch_type in ('IN', 'OUT'):
            resp = self._punch(punch_type, source='manual')
            self.assertEqual(resp.status_code, 422, resp.data)
        self._assert_no_punch()

    def test_biometric_source_is_refused_for_clock_in_and_out(self):
        for punch_type in ('IN', 'OUT'):
            resp = self._punch(punch_type, source='biometric')
            self.assertEqual(resp.status_code, 422, resp.data)
        self._assert_no_punch()

    def test_unsupported_source_values_are_refused(self):
        for source in ('system', 'kiosk', 'MANUAL', ''):
            resp = self._punch(source=source)
            self.assertEqual(resp.status_code, 422, (source, resp.data))
        self._assert_no_punch()

    def test_web_without_face_data_is_refused(self):
        resp = self._punch(source='web')
        self.assertEqual(resp.status_code, 400, resp.data)
        self._assert_no_punch()

    def test_clock_out_is_verified_like_clock_in(self):
        self.assertEqual(self._punch('IN', face_embedding=MATCHING_EMBEDDING,
                                     capture_session_id='s-in').status_code, 200)
        self.assertEqual(self._punch('OUT').status_code, 400)                        # no face data
        self.assertEqual(self._punch('OUT', face_embedding=MISMATCHED_EMBEDDING,
                                     capture_session_id='s-bad').status_code, 403)   # wrong face
        second_match = [v + 0.002 for v in REGISTERED_EMBEDDING]
        resp = self._punch('OUT', face_embedding=second_match, capture_session_id='s-out')
        self.assertEqual(resp.status_code, 200, resp.data)
        out = AttendancePunch.objects.get(employee=self.employee, punch_type='OUT')
        self.assertTrue(out.face_verified)

    def test_service_requires_face_for_every_source(self):
        from apps.attendance.services_face_matching import FaceVerificationService
        for source in ('web', 'voice', 'mobile', 'manual', 'biometric', 'system', 'anything-else'):
            outcome = FaceVerificationService.verify_for_punch(self.employee, source, None)
            self.assertTrue(outcome.required, source)
            self.assertFalse(outcome.is_match, source)

    # ── Mobile: no longer exempt ─────────────────────────────────────────────

    def test_mobile_without_face_data_is_refused_for_clock_in_and_out(self):
        resp = self._punch('IN', source='mobile')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('face verification is required', resp.data['message'].lower())
        self._assert_no_punch()
        # Clock out (after a verified clock-in) without face data is refused too.
        self.assertEqual(self._punch('IN', source='mobile', face_embedding=MATCHING_EMBEDDING,
                                     capture_session_id='m-in').status_code, 200)
        resp = self._punch('OUT', source='mobile')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('face verification is required', resp.data['message'].lower())
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee, punch_type='OUT').exists())

    def test_mobile_with_someone_elses_face_is_refused(self):
        # The reported incident: another person's face accepted on mobile.
        resp = self._punch(source='mobile', face_embedding=MISMATCHED_EMBEDDING, capture_session_id='m-bad')
        self.assertEqual(resp.status_code, 403, resp.data)
        self._assert_no_punch()

    def test_mobile_clock_in_and_out_with_matching_face_succeed(self):
        resp = self._punch('IN', source='mobile', face_embedding=MATCHING_EMBEDDING, capture_session_id='m-in')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._punch('OUT', source='mobile').status_code, 400)    # clock-out needs a face too
        second_match = [v + 0.002 for v in REGISTERED_EMBEDDING]
        resp = self._punch('OUT', source='mobile', face_embedding=second_match, capture_session_id='m-out')
        self.assertEqual(resp.status_code, 200, resp.data)
        punches = AttendancePunch.objects.filter(employee=self.employee).order_by('punched_at')
        self.assertEqual([(p.punch_type, p.source, p.face_verified) for p in punches],
                         [('IN', 'mobile', True), ('OUT', 'mobile', True)])

    def test_web_session_cannot_skip_face_by_claiming_mobile(self):
        # Same cookie-authenticated client as a browser: claiming source=mobile
        # used to skip the check entirely.
        resp = self._punch(source='mobile')
        self.assertEqual(resp.status_code, 400, resp.data)
        self._assert_no_punch()

    # ── Voice ────────────────────────────────────────────────────────────────

    def test_voice_is_verified(self):
        self.assertEqual(self._punch(source='voice').status_code, 400)
        self.assertEqual(self._punch(source='voice', face_embedding=MISMATCHED_EMBEDDING,
                                     capture_session_id='v-bad').status_code, 403)
        resp = self._punch(source='voice', face_embedding=MATCHING_EMBEDDING, capture_session_id='v-ok')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(AttendancePunch.objects.get(employee=self.employee).face_verified)

    # ── Company (tenant) isolation ───────────────────────────────────────────

    def _client_with_token(self, *, company_schema=None, as_cookie=True):
        from rest_framework_simplejwt.tokens import AccessToken
        token = AccessToken.for_user(self.employee)
        if company_schema is not None:
            token['company_schema'] = company_schema
        c = APIClient()
        if as_cookie:
            c.cookies['royal_access_token'] = str(token)
        else:
            c.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return c

    def _raw_punch(self, client):
        # A refused cross-company request runs against the public schema,
        # where the user lookup fails at the DB level (swallowed by the auth
        # class) and aborts the test's transaction. Run it inside a savepoint
        # that is always rolled back so the follow-up assertion can query.
        from django.db import transaction

        class _Rollback(Exception):
            pass

        resp = None
        try:
            with transaction.atomic():
                resp = client.post(reverse('attendance-punch'),
                                   {'punch_type': 'IN', 'attendance_mode': 'office', 'source': 'mobile',
                                    'face_embedding': MATCHING_EMBEDDING, 'capture_session_id': 't-iso'},
                                   format='json')
                raise _Rollback
        except _Rollback:
            pass
        return resp

    def test_token_pointing_at_another_company_cannot_punch(self):
        # A token claiming a different (here: non-existent) company never
        # reaches this company's data — the request is not authenticated.
        resp = self._raw_punch(self._client_with_token(company_schema='tenant_othercompany'))
        self.assertEqual(resp.status_code, 401, resp.data)
        self._assert_no_punch()

    def test_bearer_token_without_company_cookie_cannot_punch(self):
        resp = self._raw_punch(self._client_with_token(as_cookie=False))
        self.assertEqual(resp.status_code, 401, resp.data)
        self._assert_no_punch()

    def test_hr_approved_correction_still_creates_manual_punch(self):
        import datetime
        from django.utils import timezone
        from apps.attendance.models import AttendanceCorrection
        admin = make_user('facebypass.admin@test.com', password='TestPass123!', employee_id='FBA1',
                          role=make_role('admin_bypass', permission_codenames=['settings.edit', 'attendance.view',
                                                                                'attendance.create']))
        correction = AttendanceCorrection.objects.create(
            employee=self.employee, date=timezone.localdate(), punch_type='IN',
            requested_in_time=datetime.time(9, 0), reason='forgot_to_punch',
            status=AttendanceCorrection.STATUS_L2_PENDING,
        )
        hr_client = APIClient()
        _login(hr_client, 'facebypass.admin@test.com')
        resp = hr_client.patch(reverse('hr-correction-review', kwargs={'pk': correction.pk}),
                               {'action': 'approve'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        punch = AttendancePunch.objects.get(employee=self.employee)
        self.assertEqual(punch.source, AttendancePunch.SOURCE_MANUAL)
        self.assertFalse(punch.face_verified)

    def test_employee_cannot_approve_own_correction(self):
        from django.utils import timezone
        import datetime
        from apps.attendance.models import AttendanceCorrection
        correction = AttendanceCorrection.objects.create(
            employee=self.employee, date=timezone.localdate(), punch_type='IN',
            requested_in_time=datetime.time(9, 0), reason='forgot_to_punch',
            status=AttendanceCorrection.STATUS_L2_PENDING,
        )
        resp = self.client.patch(reverse('hr-correction-review', kwargs={'pk': correction.pk}),
                                 {'action': 'approve'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
        self._assert_no_punch()


class FaceRegistrationMyStatusTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client   = APIClient()
        self.employee = make_user('facestatus@test.com', role=make_role('employee'))
        _login(self.client, 'facestatus@test.com')

    def tearDown(self):
        cache.clear()

    def test_no_registration_returns_empty_data(self):
        resp = self.client.get(reverse('face-registration-me'))
        self.assertEqual(resp.status_code, 200, resp.data)
        # success() (core/responses.py) normalises a None data payload to {} —
        # shared helper behavior, not something this endpoint overrides.
        self.assertEqual(resp.data['data'], {})

    def test_approved_registration_status_is_returned(self):
        _make_approved_request(self.employee)
        resp = self.client.get(reverse('face-registration-me'))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['status'], 'approved')

    def test_returns_latest_request_when_several_exist(self):
        older = FaceRegistrationRequest.objects.create(
            employee=self.employee, face_embedding=REGISTERED_EMBEDDING,
            liveness_passed=True, status=FaceRegistrationRequest.STATUS_REJECTED,
        )
        newer = _make_approved_request(self.employee)
        resp = self.client.get(reverse('face-registration-me'))
        self.assertEqual(resp.data['data']['id'], str(newer.pk))
        self.assertNotEqual(resp.data['data']['id'], str(older.pk))


class FaceRegistrationHRRegisterTests(TestCase):
    """HR captures a face in person and registers/updates it directly,
    auto-approved — see views/face_registration_hr.py."""

    def setUp(self):
        cache.clear()
        _set_face_verification_mandatory(True)
        self.client = APIClient()
        self.hr_role = make_role('hr', permission_codenames=['facial_recognition.approve'])
        self.hr_user = make_user('hrregister-hr@test.com', role=self.hr_role, branch='Head Office')
        # Deliberately a different branch than the HR user's own, to prove
        # the picker/register endpoints are NOT branch-scoped.
        self.employee = make_user(
            'hrregister-employee@test.com', role=make_role('employee_hr_target'),
            branch='Remote Branch',
        )
        _login(self.client, 'hrregister-hr@test.com')

    def tearDown(self):
        cache.clear()

    def _register(self, **overrides):
        payload = {
            'employee_uuid': str(self.employee.pk),
            'face_embedding': REGISTERED_EMBEDDING,
            'liveness_passed': True,
            'liveness_score': 0.95,
            'consent_acknowledged': True,
        }
        payload.update(overrides)
        return self.client.post(reverse('face-registration-hr-register'), payload, format='json')

    def test_register_is_refused_when_toggle_is_off(self):
        _set_face_verification_mandatory(False)
        resp = self._register()
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertIn('contact your administrator', resp.data['message'].lower())
        self.assertFalse(FaceRegistrationRequest.objects.filter(employee=self.employee).exists())

    def test_non_approver_is_forbidden_on_all_three_endpoints(self):
        make_user('hrregister-noperm@test.com', role=make_role('employee_no_facial_perm_hr'))
        client = APIClient()
        _login(client, 'hrregister-noperm@test.com')

        self.assertEqual(
            client.get(reverse('face-registration-employee-picker')).status_code, 403,
        )
        self.assertEqual(
            client.get(reverse('face-registration-employee-status', kwargs={'employee_uuid': self.employee.pk})).status_code,
            403,
        )
        self.assertEqual(
            client.post(reverse('face-registration-hr-register'), {
                'employee_uuid': str(self.employee.pk), 'face_embedding': REGISTERED_EMBEDDING,
                'liveness_passed': True, 'consent_acknowledged': True,
            }, format='json').status_code,
            403,
        )

    def test_register_new_face_is_auto_approved(self):
        resp = self._register()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['data']['status'], 'approved')

        face_request = FaceRegistrationRequest.objects.get(employee=self.employee)
        self.assertEqual(face_request.status, FaceRegistrationRequest.STATUS_APPROVED)
        self.assertEqual(face_request.approved_by_id, self.hr_user.id)
        self.assertIsNotNone(face_request.approved_at)

    def test_updating_an_already_registered_employee_supersedes_the_old_face(self):
        self._register(face_embedding=REGISTERED_EMBEDDING)
        new_embedding = [v + 2.0 for v in REGISTERED_EMBEDDING]  # a visibly different face
        resp = self._register(face_embedding=new_embedding)
        self.assertEqual(resp.status_code, 201, resp.data)

        # Punching with the OLD face now fails; the NEW one succeeds — proves
        # the update actually took effect for the punch flow, not just the DB row.
        # A fresh client, not self.client (still authenticated as HR) — cookie
        # auth doesn't reset with Django's session-oriented .logout().
        employee_client = APIClient()
        _login(employee_client, 'hrregister-employee@test.com')

        old_face_resp = employee_client.post(reverse('attendance-punch'), {
            'punch_type': 'IN', 'attendance_mode': 'wfh', 'face_embedding': REGISTERED_EMBEDDING,
        }, format='json')
        self.assertEqual(old_face_resp.status_code, 403, old_face_resp.data)

        new_face_resp = employee_client.post(reverse('attendance-punch'), {
            'punch_type': 'IN', 'attendance_mode': 'wfh', 'face_embedding': new_embedding,
        }, format='json')
        self.assertEqual(new_face_resp.status_code, 200, new_face_resp.data)

    def test_employee_picker_is_not_branch_scoped(self):
        resp = self.client.get(reverse('face-registration-employee-picker'))
        self.assertEqual(resp.status_code, 200, resp.data)
        emails = {row['email'] for row in resp.data['data']['results']}
        # employee is on 'Remote Branch', hr_user is on 'Head Office' — visible
        # anyway proves this isn't scoped like accounts.EmployeeListCreateView.
        self.assertIn('hrregister-employee@test.com', emails)

    def test_employee_picker_search_filters_by_name(self):
        resp = self.client.get(reverse('face-registration-employee-picker'), {'search': 'hrregister-employee'})
        emails = {row['email'] for row in resp.data['data']['results']}
        self.assertEqual(emails, {'hrregister-employee@test.com'})

    def test_employee_status_endpoint_reflects_registration(self):
        no_reg_resp = self.client.get(
            reverse('face-registration-employee-status', kwargs={'employee_uuid': self.employee.pk})
        )
        self.assertEqual(no_reg_resp.data['data'], {})

        self._register()
        resp = self.client.get(
            reverse('face-registration-employee-status', kwargs={'employee_uuid': self.employee.pk})
        )
        self.assertEqual(resp.data['data']['status'], 'approved')

    def test_register_for_unknown_employee_is_not_found(self):
        resp = self._register(employee_uuid='00000000-0000-0000-0000-000000000000')
        self.assertEqual(resp.status_code, 404, resp.data)
