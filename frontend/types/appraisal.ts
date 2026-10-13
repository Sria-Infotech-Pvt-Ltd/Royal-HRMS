/** One employee's appraisal for a cycle, as the Reporting Manager's workspace sees it. */
export interface TeamReview {
  id: string;
  employee: string;
  employee_name: string;
  employee_code: string;
  cycle_name: string;
  cycle_self_review_due: string | null;
  cycle_manager_review_due: string | null;
  key_strengths: string;
  development_areas: string;
  support_needed: string;
  next_cycle_goal: string;
  self_rating: string;
  self_submitted_at: string | null;
  manager_rating: string;
  manager_notes: string;
  manager_development_plan: string;
  manager_next_checkin: string | null;
  manager_submitted_at: string | null;
  returned_at: string | null;
  return_reason: string;
  hr_calibrated_at: string | null;
  final_rating: string;
  calibration_note: string;
  published_at: string | null;
  acknowledged_at: string | null;
  status: "not_started" | "returned" | "self_review" | "hr_calibration" | "published" | "completed";
  status_display: string;
}

/** A goal with the employee's own self-review of it. */
export interface ReviewGoal {
  id: string;
  title: string;
  description: string;
  target_metric: string;
  weight_percent: number | null;
  self_rating: string;
  outcome_measure: string;
  evidence_reference: string;
  self_comments: string;
}

export const RATING_OPTIONS: { value: string; label: string }[] = [
  { value: "1", label: "1 · Below expectations" },
  { value: "2", label: "2 · Developing" },
  { value: "3", label: "3 · Meets expectations" },
  { value: "4", label: "4 · Exceeds expectations" },
  { value: "5", label: "5 · Outstanding" },
];

/** What stage a team member's review is in, from the manager's point of view. */
export function managerStageLabel(status: TeamReview["status"]): string {
  switch (status) {
    case "not_started":    return "Waiting for self-review";
    case "returned":       return "Returned to employee";
    case "self_review":    return "Ready for your assessment";
    case "hr_calibration": return "With HR calibration";
    case "published":      return "Published · acknowledgement due";
    case "completed":      return "Acknowledged";
  }
}
