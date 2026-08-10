// Biometric consent notice shown before any face capture begins (both the
// self-service flow in FaceRegistrationModal and the HR-witnessed flow in
// HRFaceCaptureModal) — never after capture, so consent is obtained before
// data collection starts, not just before submission.
//
// FACE_CONSENT_TEXT_VERSION must be bumped whenever the wording below
// changes, and kept in sync with the backend's own copy of the same
// constant (apps.attendance.models.FACE_CONSENT_TEXT_VERSION) — there's no
// shared source of truth across the Python/TS boundary, so this match is
// maintained by convention. The version (not the text itself) is what's
// actually persisted server-side (FaceRegistrationRequest.consent_text_version),
// so a future wording change never silently reinterprets what an employee
// already agreed to under the current text.
export const FACE_CONSENT_TEXT_VERSION = "v1";

export const FACE_CONSENT_NOTICE_EMPLOYEE =
  "I understand my facial data will be captured and converted into a numeric " +
  "face signature (not a photo or video) to verify my identity for clock-in " +
  "and clock-out. This signature is stored securely, used only for attendance " +
  "verification, and is never shared outside this purpose. I can ask HR to " +
  "update it at any time, and it will be deleted when my employment ends.";

export const FACE_CONSENT_NOTICE_HR =
  "I confirm the employee has been informed that their facial data will be " +
  "captured and converted into a numeric face signature (not a photo or " +
  "video) to verify their identity for clock-in and clock-out, that it is " +
  "stored securely and used only for that purpose, and that they have " +
  "verbally consented to this capture before I proceed.";
