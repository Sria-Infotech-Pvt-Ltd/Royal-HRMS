// Field names mirror the raw API response (snake_case) — same convention
// as types/orgChart.ts and the ApiEmployee/ApiProfile shapes elsewhere.
export interface WorkFromHomeRequest {
  id:               string;
  start_date:       string;
  end_date:         string;
  reason:           string;
  location_label:   string;
  latitude:         string;
  longitude:        string;
  status:           "pending" | "l2_pending" | "approved" | "rejected" | "cancelled";
  employee_name:    string;
  employee_code:    string;
  employee_dept:    string;
  employee_branch:  string;
  l1_approver_name: string;
  l1_status:        "approved" | "rejected" | null;
  l1_remarks:       string;
  l1_actioned_at:   string | null;
  l2_approver_name: string;
  l2_status:        "approved" | "rejected" | null;
  l2_remarks:       string;
  l2_actioned_at:   string | null;
  created_at:       string;
  can_approve:      boolean;
  can_cancel:       boolean;
}

export const WFH_STATUS_LABELS: Record<WorkFromHomeRequest["status"], string> = {
  pending:    "Pending",
  l2_pending: "L2 Pending",
  approved:   "Approved",
  rejected:   "Rejected",
  cancelled:  "Cancelled",
};
