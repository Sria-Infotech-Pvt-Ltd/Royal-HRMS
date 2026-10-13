export type PersonnelActionType = "promotion" | "org_assignment" | "pay_change" | "confirmation";

export type PersonnelActionStatus = "pending" | "applied" | "rejected" | "cancelled" | "failed";

export type PersonnelActionStepStatus = "pending" | "approved" | "rejected" | "skipped";

export interface PersonnelActionStep {
  key: "manager" | "hr" | "payroll";
  label: string;
  status: PersonnelActionStepStatus;
  decided_by_id: string | null;
  decided_by_name: string;
  decided_at: string | null;
  note: string;
}

/** BEFORE / AFTER values keyed by field (position, annual_ctc, reporting_manager, work_location, employment_status). */
export type PersonnelActionValues = Partial<Record<
  "position" | "annual_ctc" | "reporting_manager" | "work_location" | "employment_status",
  string
>>;

export interface PersonnelActionRequest {
  id: string;
  employee: { id: string; code: string; name: string; designation: string };
  action_type: PersonnelActionType;
  action_label: string;
  reason: string;
  effective_from: string;
  before: PersonnelActionValues;
  after: PersonnelActionValues;
  raised_by_name: string;
  status: PersonnelActionStatus;
  status_display: string;
  steps: PersonnelActionStep[];
  current_step: number;
  current_step_label: string;
  route: string;
  decision_note: string;
  apply_error: string;
  created_at: string;
  applied_at: string | null;
  can_decide: boolean;
  can_cancel: boolean;
}
