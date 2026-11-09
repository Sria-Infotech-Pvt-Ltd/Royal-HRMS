import type { AccountStatus, EmploymentStage, OnboardingStage } from "@/types/employeeLifecycle";

export const STAGE_LABEL: Record<EmploymentStage, string> = {
  pre_joining: "Pre-Joining", active: "Active", terminated: "Terminated", unknown: "Unknown (Date Missing)",
};

export const ACCOUNT_LABEL: Record<AccountStatus, string> = {
  invitation_pending: "Invitation Pending", active: "Active", disabled: "Disabled",
};

export const ONBOARDING_LABEL: Record<OnboardingStage, string> = {
  not_started: "Not Started", in_progress: "In Progress", awaiting_review: "Awaiting Review",
  needs_revision: "Needs Revision", completed: "Completed",
};

/** Directory filter values that map to the `employment_stage` query parameter instead of `status`. */
export const STAGE_FILTER_PREFIX = "stage:";
export type StageFilterValue = `stage:${Exclude<EmploymentStage, "active">}`;

export function isStageFilter(value: string): value is StageFilterValue {
  return value.startsWith(STAGE_FILTER_PREFIX);
}

/** Query parameters for a directory filter value. The stats endpoint has no stage filter, so it gets none. */
export function filterQueryParams(value: string, forStats = false): Record<string, string> {
  if (value === "all") return {};
  if (isStageFilter(value)) return forStats ? {} : { employment_stage: value.slice(STAGE_FILTER_PREFIX.length) };
  return { status: value };
}

export type LifecycleNoteTone = "info" | "warn" | "crit";

export interface LifecycleNote {
  text: string;
  tone: LifecycleNoteTone;
}

function formatShortDate(iso: string): string {
  const [year, month, day] = iso.split("-");
  return year && month && day ? `${day}/${month}/${year}` : iso;
}

/** The small line shown under a directory status pill when the employment stage needs saying (null = nothing extra to show). */
export function lifecycleNote(
  stage: EmploymentStage | undefined, dateOfJoining: string, isLocked = false,
): LifecycleNote | null {
  if (stage === "pre_joining") return { text: dateOfJoining ? `Joins ${formatShortDate(dateOfJoining)}` : "Pre-Joining", tone: "info" };
  if (stage === "unknown") return { text: "Joining date missing — HR to correct", tone: "warn" };
  if (stage === "terminated") return { text: "Employment ended", tone: "crit" };
  if (isLocked) return { text: "Account locked", tone: "warn" };
  return null;
}

/** True when `iso` (YYYY-MM-DD) is after today in the viewer's calendar. Display only: the server decides what is allowed. */
export function isFutureDate(iso: string | null | undefined, now: Date = new Date()): boolean {
  if (!iso) return false;
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  return iso > today;
}
