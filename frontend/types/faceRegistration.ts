// ─── Face registration ─────────────────────────────────────────────────────
// Types for the employee face-enrollment approval workflow. Mirrors
// apps.attendance.models.FaceRegistrationRequest and
// apps.attendance.serializers_face_registration on the backend.
//
// The raw face_embedding vector is never part of these types on purpose —
// FaceRegistrationReadSerializer excludes it from every response, and the
// frontend never needs it once a request has been submitted.

export type FaceRegistrationStatus = "pending" | "approved" | "rejected";

export interface FaceRegistrationRequest {
  id:                      string;
  employee_name:           string;
  employee_email:          string;
  liveness_passed:         boolean;
  liveness_score:          number | null;
  embedding_model_version: string;
  status:                  FaceRegistrationStatus;
  approved_by_name:        string;
  approved_at:             string | null;
  notes:                   string;
  created_at:              string;
}

/** Body for POST /api/attendance/face-registration/ — never a raw image. */
export interface FaceRegistrationSubmitPayload {
  face_embedding:       number[];
  liveness_passed:      boolean;
  liveness_score:       number | null;
  /** Must be true — the backend rejects the request otherwise. Confirms the
   *  employee ticked the consent notice shown before capture started. */
  consent_acknowledged: boolean;
}

/** Body for PATCH /api/attendance/face-registration/<id>/review/ */
export interface FaceRegistrationDecisionPayload {
  status: Extract<FaceRegistrationStatus, "approved" | "rejected">;
  notes?: string;
}

export interface PaginatedFaceRegistrations {
  results:     FaceRegistrationRequest[];
  count:       number;
  page:        number;
  page_size:   number;
  total_pages: number;
}

// ─── HR-initiated registration (register/update on someone's behalf) ──────
// Mirrors FaceRegistrationEmployeeSerializer — deliberately a minimal
// projection, not the full employee profile (no bank/address/PII fields).
export interface FaceRegistrationEmployee {
  uuid:        string;
  employee_id: string;
  full_name:   string;
  email:       string;
  branch:      string;
  department:  string;
  designation: string;
}

export interface PaginatedFaceRegistrationEmployees {
  results:     FaceRegistrationEmployee[];
  count:       number;
  page:        number;
  page_size:   number;
  total_pages: number;
}

/** Body for POST /api/attendance/face-registration/register/ */
export interface FaceRegistrationHRRegisterPayload {
  employee_uuid:        string;
  face_embedding:       number[];
  liveness_passed:      boolean;
  liveness_score:       number | null;
  /** Must be true — the backend rejects the request otherwise. Confirms HR
   *  obtained the employee's consent in person before this witnessed capture. */
  consent_acknowledged: boolean;
}
