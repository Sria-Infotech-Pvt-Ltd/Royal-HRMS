// What the server says about Face ID for the signed-in person (GET /attendance/face-verification/status/). The text in
// `message` is the one instruction to show, whichever screen it is; screens must not write their own.

export type FaceIdMode = "self_service" | "hr_in_person" | "self_service_hr_approval";
export type FaceIdFallbackPolicy = "none" | "days_after_joining" | "until_approved";
export type FaceIdState = "approved" | "pending" | "rejected" | "not_registered";

export interface FaceIdGuidance {
  is_mandatory: boolean;
  registration_mode: FaceIdMode;
  state: FaceIdState;
  /** The employee may register their own Face ID (and has no request waiting). */
  can_self_register: boolean;
  /** A face capture is needed to clock in (an approved registration exists). */
  requires_face_to_punch: boolean;
  message: string;
  /** A punch from the office is allowed without a face match right now (flagged for HR). */
  fallback_active: boolean;
  fallback_until: string | null;
  /** What HR / an admin should know about how registration works here. */
  hr_note: string;
}

/** Face ID status and next steps returned when a hire is completed. */
export interface FaceIdHireSummary {
  is_mandatory: boolean;
  registration_mode: FaceIdMode;
  state: FaceIdState;
  employee_message: string;
  hr_next_step: string;
  fallback_active: boolean;
  fallback_until: string | null;
}

export const FACE_ID_MODE_LABELS: Record<FaceIdMode, string> = {
  self_service: "Employee registers (active immediately)",
  hr_in_person: "HR registers in person",
  self_service_hr_approval: "Employee registers, HR approves",
};

export const FACE_ID_FALLBACK_LABELS: Record<FaceIdFallbackPolicy, string> = {
  none: "No fallback — a Face ID is always required",
  days_after_joining: "Allow office punches without Face ID for N days after joining",
  until_approved: "Allow office punches without Face ID until a Face ID is approved",
};
