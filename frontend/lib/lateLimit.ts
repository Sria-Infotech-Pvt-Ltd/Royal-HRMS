// Maximum Late Arrivals Per Month — tracking only (backend
// apps/attendance/services_late_limit.py). It never changes LOP; the
// late-mark LOP rule lives in Settings → Attendance Rules.

export type LateLimitStatus = "within" | "reached" | "exceeded";

export interface LateLimitSetting {
  enabled:    boolean;
  maximum:    number;
  configured: boolean;   // false until Attendance Rules have been saved once
  can_edit:   boolean;
}

export interface LateLimitSummary {
  enabled:       boolean;
  maximum:       number;
  late_arrivals: number;
  remaining:     number | null;
  status:        LateLimitStatus | null;
  status_label:  string | null;
  year:          number;
  month:         number;
}

export interface LateLimitEmployee {
  employee:      string;
  name:          string;
  employee_code: string;
  branch:        string;
  department:    string;
  late_arrivals: number;
  over_by:       number;
  status:        LateLimitStatus;
  status_label:  string;
}

export const LATE_LIMIT_MAX = 31;

export const LATE_LIMIT_BADGE: Record<LateLimitStatus, string> = {
  within:   "badge badge-success",
  reached:  "badge badge-warn",
  exceeded: "badge badge-error",
};

/** Validation for the maximum field (the server repeats it). */
export function maximumError(raw: string): string | null {
  const text = raw.trim();
  if (!text) return "Enter the maximum.";
  if (!/^\d+$/.test(text)) return "Enter a whole number.";
  const n = Number(text);
  if (n < 1) return "Enter at least 1.";
  if (n > LATE_LIMIT_MAX) return `Enter at most ${LATE_LIMIT_MAX}.`;
  return null;
}
