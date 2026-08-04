export type ApprovalWorkflowType = "leave" | "expense" | "attendance_correction";

export interface WorkflowMatrixRow {
  workflow_type:     ApprovalWorkflowType;
  workflow_label:    string;
  l1_approver_role:  number | null;
  l1_approver_label: string;
  l1_approver_id:    string | null;
  l1_approver_name:  string | null;
  l1_is_override:    boolean;
  l2_approver_role:  number | null;
  l2_approver_label: string;
  l2_approver_id:    string | null;
  l2_approver_name:  string | null;
  l2_is_override:    boolean;
}

export interface GlobalApprovalRule {
  workflow_type:     ApprovalWorkflowType;
  workflow_label:    string;
  l1_approver_role:  number | null;
  l1_approver_label: string;
  l2_approver_role:  number | null;
  l2_approver_label: string;
}
