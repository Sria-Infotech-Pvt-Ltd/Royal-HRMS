// What the Punch In / Punch Out button must do about Face ID, from the server's one Face ID answer
// (GET /attendance/face-verification/status/ -> useFaceVerificationStatus). Pure so every combination of
// organisation mode, employee state and fallback can be tested without a browser.
//
// The server already folds the organisation's registration mode (self_service / hr_in_person /
// self_service_hr_approval) and fallback policy (none / days_after_joining / until_approved) into these flags:
//   requires_face_to_punch - this person has an approved, active Face ID, so a face capture is needed
//   fallback_active        - no approved Face ID yet, but the fallback currently allows an office punch without one
// so the client never re-implements that policy.
export interface FaceGateInput {
  isMandatory: boolean;
  requiresFaceToPunch: boolean;
  fallbackActive: boolean;
}

export interface FaceGate {
  /** Open the face camera before punching. */
  faceVerificationRequired: boolean;
  /** Stop the punch before GPS or the camera: Face ID is mandatory, this person has no approved one (not registered,
   *  pending or rejected) and no fallback applies. They are told to register first and come back. */
  faceRegistrationMissing: boolean;
}

export function faceGateFor({ isMandatory, requiresFaceToPunch, fallbackActive }: FaceGateInput): FaceGate {
  return {
    faceVerificationRequired: isMandatory && requiresFaceToPunch,
    faceRegistrationMissing: isMandatory && !requiresFaceToPunch && !fallbackActive,
  };
}
