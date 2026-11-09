// Biometric consent notice shown before any face capture begins (both the
// self-service flow in FaceRegistrationModal and the HR-witnessed flow in
// HRFaceCaptureModal) — never after capture, so consent is obtained before
// data collection starts, not just before submission.
//
// This file holds the WORDING only. It deliberately has NO version constant: the version is defined once, on the
// server (apps.attendance.models.FACE_CONSENT_TEXT_VERSION), and the server stamps it on every NEW registration
// (FaceRegistrationRequest.consent_text_version) - the browser never sends or chooses it, so a second copy here could
// only drift. Existing registrations keep the version they were stamped with (v1 rows stay v1).
//
// If you change the wording below you MUST bump the backend constant: backend/apps/attendance/tests_face_consent_version.py
// pins a hash of this wording to the current version and fails until the version is bumped and the new hash recorded.
// v2 (2026-11-03): wording changed from "clock-in / clock-out" to "Punch In / Punch Out" to match the button labels.

export const FACE_CONSENT_NOTICE_EMPLOYEE =
  "I understand my facial data will be captured and converted into a numeric " +
  "face signature (not a photo or video) to verify my identity for Punch In " +
  "and Punch Out. This signature is stored securely, used only for attendance " +
  "verification, and is never shared outside this purpose. I can ask HR to " +
  "update it at any time, and it will be deleted when my employment ends.";

export const FACE_CONSENT_NOTICE_HR =
  "I confirm the employee has been informed that their facial data will be " +
  "captured and converted into a numeric face signature (not a photo or " +
  "video) to verify their identity for Punch In and Punch Out, that it is " +
  "stored securely and used only for that purpose, and that they have " +
  "verbally consented to this capture before I proceed.";
