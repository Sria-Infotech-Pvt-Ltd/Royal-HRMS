export type ApproverKind = "reporting_manager" | "hr" | "person" | "";

export type ApprovalWorkflowType = "leave" | "expense" | "attendance_correction";

export interface WorkflowMatrixRow {
  workflow_type:     ApprovalWorkflowType;
  workflow_label:    string;
  l1_approver_kind:  ApproverKind;
  l1_approver_label: string;
  l1_approver_id:    string | null;
  l1_approver_name:  string | null;
  l1_is_override:    boolean;
  l2_approver_kind:  ApproverKind;
  l2_approver_label: string;
  l2_approver_id:    string | null;
  l2_approver_name:  string | null;
  l2_is_override:    boolean;
}

/** Someone who may be named as a workflow's approver: active, with that workflow's approve capability. */
export interface ApprovalRulePerson {
  id:          string;
  employee_id: string;
  full_name:   string;
  department:  string;
}

export interface GlobalApprovalRule {
  workflow_type:       ApprovalWorkflowType;
  workflow_label:      string;
  l1_approver_kind:    ApproverKind;
  l1_approver_label:   string;
  /** Set only when l1_approver_kind is "person". */
  l1_approver_user_id: string | null;
  l2_approver_kind:    ApproverKind;
  l2_approver_label:   string;
  l2_approver_user_id: string | null;
  /** Everyone the dropdown offers next to "Reporting manager" and "HR partner". */
  eligible_approvers:  ApprovalRulePerson[];
}
