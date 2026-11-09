/** Derived lifecycle statuses sent by the employee APIs (see backend services_lifecycle_status). All optional: older cached pages keep working. */
export type EmploymentStage = "pre_joining" | "active" | "terminated" | "unknown";
export type AccountStatus = "invitation_pending" | "active" | "disabled";
export type OnboardingStage = "not_started" | "in_progress" | "awaiting_review" | "needs_revision" | "completed";

export interface EmployeeLifecycle {
  employment_stage?: EmploymentStage;
  employment_stage_label?: string;
  /** True when the joining date is blank: HR has to correct it. */
  date_missing?: boolean;
  account_status?: AccountStatus;
  /** Temporarily locked (too many failed logins). Not the same as Disabled. */
  account_locked?: boolean;
  onboarding_stage?: OnboardingStage;
}

export interface EmploymentStageCounts {
  pre_joining: number;
  active: number;
  terminated: number;
  unknown: number;
}
