// A Face ID registration can only be rejected with a written reason: the employee is told why. The API enforces this
// too (FaceRegistrationDecisionSerializer); this gives the approver the message before the request is even sent.
export const REJECTION_REASON_REQUIRED = "Please give a reason for rejecting this Face ID registration.";

/** The validation message for a rejection reason, or "" when it is acceptable. */
export function rejectionProblem(remarks: string): string {
  return remarks.trim() ? "" : REJECTION_REASON_REQUIRED;
}
