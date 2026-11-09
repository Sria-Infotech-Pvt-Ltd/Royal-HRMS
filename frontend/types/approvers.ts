// Approver assignments: reporting manager, L1 approver and L2 HR approver (backend: services_approver_assignment.py).

export type ApproverRole = "reporting_manager" | "l1" | "l2";

/** Someone offered in a dropdown, or named on a screen. `id` and the detail fields are absent in the employee-facing form. */
export interface PersonRef {
  id?: string;
  employee_id?: string;
  full_name: string;
  role: string;
  branch?: string;
  is_active?: boolean;
}

export interface ApproverOption extends PersonRef {
  id: string;
  employee_id: string;
  department: string;
}

/** What an empty L1 / L2 choice means: the global approval rule for leave. */
export interface ApprovalRuleSummary { l1: string; l2: string; l1_kind: string; l2_kind: string }

export interface ApproverOptionsPage { results: ApproverOption[]; rule: ApprovalRuleSummary }

export type StageStatus = "assigned" | "skipped" | "missing";

export interface ApprovalStage {
  stage: "l1" | "l2";
  label: string;
  status: StageStatus;
  user: PersonRef | null;
  note: string;
}

export interface ApprovalChain {
  workflow: string;
  reporting_manager: (PersonRef & { source: string }) | null;
  stages: ApprovalStage[];
  warnings: string[];
  blocking: string[];
  can_submit: boolean;
}

export interface ApproverAssignments {
  employee: { id: string; employee_id: string; full_name: string };
  can_edit: boolean;
  reporting_manager: { assigned: PersonRef | null; effective: (PersonRef & { source: string }) | null };
  l1_approver: { assigned: PersonRef | null; effective: PersonRef | null };
  l2_hr_approver: { assigned: PersonRef | null; effective: PersonRef | null };
  rule: ApprovalRuleSummary;
  chain: ApprovalChain;
}

/** The three choices as the forms hold them: "" means "not chosen" (follow the org chart / the approval rule). */
export interface ApproverSelection {
  reporting_manager_id: string;
  l1_approver_id: string;
  hr_id: string;
}

export const EMPTY_APPROVER_SELECTION: ApproverSelection = { reporting_manager_id: "", l1_approver_id: "", hr_id: "" };
