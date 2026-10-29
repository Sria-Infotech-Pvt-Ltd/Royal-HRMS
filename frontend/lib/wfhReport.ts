// Work From Home — medical proof check and the daily work report
// (company policy sections 6 and 7).

export const WFH_PROOF_MAX_BYTES = 5 * 1024 * 1024;
const WFH_PROOF_TYPES = ["application/pdf", "image/jpeg", "image/png"];

export function wfhMedicalProofError(isMedical: boolean, file: { size: number; type: string } | null): string | null {
  if (!isMedical) return null;
  if (!file) return "Attach a medical proof, report or prescription.";
  if (!WFH_PROOF_TYPES.includes(file.type)) return "Medical proof must be a PDF, JPG or PNG file.";
  if (file.size > WFH_PROOF_MAX_BYTES) return "Medical proof must be 5 MB or smaller.";
  return null;
}

export type ReviewStatus = "pending" | "full_day" | "half_day" | "not_accepted";

export interface WfhDailyReport {
  id: number;
  date: string;
  completed_work: string;
  pending_work: string;
  updates: string;
  submitted_at: string;
  submitted_late: boolean;
  review_status: ReviewStatus;
  reviewed_by_name: string;
  reviewed_at: string | null;
  review_remarks: string;
  employee_name: string;
  employee_code: string;
  can_review: boolean;
}

export const REVIEW_LABEL: Record<ReviewStatus, string> = {
  pending:      "Pending review",
  full_day:     "Accepted — Full Day",
  half_day:     "Accepted — Half Day",
  not_accepted: "Not accepted",
};

export function reportFormError(completed: string): string | null {
  return completed.trim() ? null : "Describe the work you completed today.";
}

export function reviewError(outcome: ReviewStatus | "", remarks: string): string | null {
  if (!outcome || outcome === "pending") return "Choose Full Day, Half Day or Not accepted.";
  if (outcome === "not_accepted" && !remarks.trim()) return "Give a reason when not accepting a report.";
  return null;
}
