// Shared types for the "Perform an action" modal and its per-action-type
// field subcomponents (kept in one place so the five field components and
// the orchestrator all agree on the same shapes).

export type ActionType =
  | "promotion" | "org_assignment" | "pay_change" | "confirmation" | "separation";

export interface ReasonOption {
  value: string;
  label: string;
}

/** GET /employees/{code}/ 's response shape — only the fields this modal reads. */
export interface EmployeeDetailSnapshot {
  id: string;
  uuid: string;
  position_id: string | null;
  org_unit_id: string | null;
  designation: string;
  department: string;
  branch: string;
  work_location: string;
  employment_status: string;
  reporting_manager: { id: string; uuid: string | null; name: string } | null;
}

/** One row from GET /employees/{code}/action-history/ — used only for the
 * subtitle's "current record runs X to Y" — real data, not invented. */
export interface ActionHistoryRow {
  effective_from: string;
  effective_to: string;
  is_current: boolean;
}

/** One row this modal's "BEFORE → AFTER" and "not changed by this action"
 * sections render — built by the orchestrator per action type. */
export interface FieldDiffRow {
  key: string;
  label: string;
  before: string;
  after: string | null; // null = unchanged
}

// ── Reason option lists — new categorisation choices added for this modal,
// not previously defined anywhere in the codebase (mirrored 1:1 against the
// backend's PromotionRecord.REASON_CHOICES / accounts.views.CONFIRMATION_REASON_CHOICES
// so the value sent always matches what the API accepts). ──
export const PROMOTION_REASONS: ReasonOption[] = [
  { value: "performance_based", label: "Performance based" },
  { value: "role_change",       label: "Role change" },
  { value: "market_correction", label: "Market correction" },
  { value: "restructuring",     label: "Restructuring" },
  { value: "other",             label: "Other" },
];

export const ORG_ASSIGNMENT_REASONS: ReasonOption[] = [
  { value: "team_restructuring", label: "Team restructuring" },
  { value: "manager_change",     label: "Manager change" },
  { value: "location_transfer",  label: "Location transfer" },
  { value: "department_change",  label: "Department change" },
  { value: "other",               label: "Other" },
];

// Pay change reuses the CtcRevisionReason enum SalaryTab.tsx already sends
// to POST /payroll/employee-salary/ — not a new list, see types/payroll.ts.
export const PAY_CHANGE_REASONS: ReasonOption[] = [
  { value: "promotion",         label: "Promotion" },
  { value: "increment",         label: "Annual increment" },
  { value: "market_correction", label: "Market correction" },
  { value: "other",             label: "Other" },
];

export const CONFIRMATION_REASONS: ReasonOption[] = [
  { value: "probation_completed", label: "Probation completed" },
  { value: "extended_probation",  label: "Extended probation" },
  { value: "other",                label: "Other" },
];

export const ACTION_LABELS: Record<ActionType, string> = {
  promotion:       "Promotion",
  org_assignment:  "Org assignment",
  pay_change:      "Pay change",
  confirmation:    "Confirmation",
  separation:      "Separation",
};

// Real approval gate each action already requires today, mirrored from the
// permission/workflow this codebase actually enforces server-side (see each
// action's endpoint): Promotion/Org assignment/Confirmation are gated by a
// single permission check with no queued approval step; Pay change likewise;
// Separation alone has a genuine multi-stage SeparationApprovalStage chain.
export function approvalRouteFor(action: ActionType, reportingManagerName: string | null, isManager: boolean): string {
  switch (action) {
    case "promotion":
      return "Requires employees.edit — applied directly by whoever has that permission (typically the reporting manager or HR); no queued approval step exists for this action yet.";
    case "org_assignment":
      return `Requires employees.edit${reportingManagerName ? ` — currently held by ${reportingManagerName} or HR` : ""}; no queued approval step exists for this action yet.`;
    case "pay_change":
      return "Requires payroll.edit — typically an HR Business Partner or Payroll Admin; no queued approval step exists for this action yet.";
    case "confirmation":
      return "Requires employees.confirm — typically the reporting manager; no queued approval step exists for this action yet.";
    case "separation":
      return isManager
        ? "HR, then Branch Admin (this employee is a manager, per the real separation approval chain)."
        : "Reporting manager, then HR (the real separation approval chain for this employee)."
    ;
    default:
      return "";
  }
}

export function reversibilityNote(action: ActionType): { text: string; tone: "purple" | "amber" } {
  switch (action) {
    case "promotion":
      return { tone: "purple", text: "Reversible. A correction action delimits this record and restores the previous position; the history keeps both." };
    case "org_assignment":
      return { tone: "purple", text: "Reversible. Record a further org assignment to move the employee back." };
    case "pay_change":
      return { tone: "purple", text: "Reversible going forward, but any payroll run already processed on this record must be corrected through arrears." };
    case "confirmation":
      return { tone: "purple", text: "Reversible. Probation can be re-opened with a further confirmation action." };
    case "separation":
      return { tone: "amber", text: "Not reversible. Undoing a separation requires a fresh Hire action and a new employee record — the original number is not reissued." };
  }
}
