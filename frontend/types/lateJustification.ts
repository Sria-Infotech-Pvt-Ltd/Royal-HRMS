// Late-arrival justification — an AttendanceCorrection with kind
// "late_justification" (backend apps/attendance/services_late_justification.py).

export type LateReason = "medical" | "transport" | "personal" | "other";

export type LateJustificationStatus = "pending" | "l2_pending" | "approved" | "rejected" | "resubmit";

/** One row from /attendance/corrections/ or /attendance/corrections/my/ (?kind=late_justification). */
export interface LateJustificationRow {
  id:                 string;
  kind:               "late_justification";
  employee_id:        string;            // employee code
  name:               string;
  department:         string;
  branch:             string;
  date:               string;            // YYYY-MM-DD
  original_in:        string | null;     // the real punch-in, never changed
  original_out:       string | null;
  reason:             LateReason;
  reason_label:       string;
  explanation:        string;
  status:             LateJustificationStatus;
  status_label:       string;
  l1_approver_name:   string | null;
  l1_status:          "approved" | "rejected" | "resubmit" | null;
  l1_remarks:         string;
  l2_approver_name:   string | null;
  l2_status:          "approved" | "rejected" | "resubmit" | null;
  l2_remarks:         string;
  can_action:         boolean;
  reviewed_by:        string | null;
  reviewed_at:        string | null;
  created_at:         string;
  has_document:       boolean;
  /** Only true for the employee and users with medical-proof access — the file is never linked otherwise. */
  can_view_document:  boolean;
  document_name:      string;
  proof_required:     boolean;
  missing_proof:      boolean;
  rejection_reason:   string;
  resubmission_count: number;
  resubmit_by:        string | null;
  can_resubmit:       boolean;
  late_excused:       boolean;
  attendance_status:  string | null;
}
