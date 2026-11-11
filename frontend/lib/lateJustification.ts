// Late-arrival justification: shared labels and client-side checks. The
// server repeats every check (including the file's real content), these only
// give quicker feedback.

import type { LateJustificationStatus, LateReason } from "@/types/lateJustification";

export const LATE_REASONS: { value: LateReason; label: string }[] = [
  { value: "medical",   label: "Medical" },
  { value: "transport", label: "Transport" },
  { value: "personal",  label: "Personal" },
  { value: "other",     label: "Other" },
];

export const LATE_STATUS: Record<LateJustificationStatus, { label: string; cls: string }> = {
  pending:    { label: "Pending",               cls: "badge badge-warn" },
  l2_pending: { label: "Pending (HR)",          cls: "badge badge-warn" },
  approved:   { label: "Approved",              cls: "badge badge-success" },
  rejected:   { label: "Rejected",              cls: "badge badge-error" },
  resubmit:   { label: "Resubmission Required", cls: "badge badge-info" },
};

export const PROOF_MAX_BYTES = 5 * 1024 * 1024;
export const PROOF_ACCEPT = ".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png";
export const EXPLANATION_MIN = 10;
export const EXPLANATION_MAX = 1000;

export function proofError(file: File | null): string | null {
  if (!file) return null;
  if (!/\.(pdf|jpe?g|png)$/i.test(file.name)) return "Upload a PDF, JPG or PNG file.";
  if (file.size === 0) return "The file is empty.";
  if (file.size > PROOF_MAX_BYTES) return "The file must be 5 MB or smaller.";
  return null;
}

export interface LateFormErrors { reason?: string; explanation?: string; document?: string }

/** `hasExistingProof`: a resubmission may keep the proof already on file. */
export function lateFormErrors(reason: string, explanation: string, file: File | null,
  hasExistingProof = false): LateFormErrors {
  const errors: LateFormErrors = {};
  if (!LATE_REASONS.some(r => r.value === reason)) errors.reason = "Choose a reason.";
  const text = explanation.trim();
  if (text.length < EXPLANATION_MIN) errors.explanation = `Explain what happened (at least ${EXPLANATION_MIN} characters).`;
  else if (text.length > EXPLANATION_MAX) errors.explanation = `Keep it under ${EXPLANATION_MAX} characters.`;
  const fileErr = proofError(file);
  if (fileErr) errors.document = fileErr;
  else if (reason === "medical" && !file && !hasExistingProof) errors.document = "Medical reasons need proof (PDF, JPG or PNG).";
  return errors;
}

/** The reason a reviewer gave when rejecting or asking for a resubmission. */
export function reviewTrail(r: { l1_status: string | null; l1_remarks: string; l1_approver_name: string | null;
  l2_status: string | null; l2_remarks: string; l2_approver_name: string | null }): string[] {
  const verb = (s: string | null) => s === "approved" ? "approved" : s === "rejected" ? "rejected" : s === "resubmit" ? "asked to resubmit" : "";
  const out: string[] = [];
  if (r.l1_status) out.push(`Manager${r.l1_approver_name ? ` (${r.l1_approver_name})` : ""} ${verb(r.l1_status)}${r.l1_remarks ? `: ${r.l1_remarks}` : ""}`);
  if (r.l2_status) out.push(`HR${r.l2_approver_name ? ` (${r.l2_approver_name})` : ""} ${verb(r.l2_status)}${r.l2_remarks ? `: ${r.l2_remarks}` : ""}`);
  return out;
}
