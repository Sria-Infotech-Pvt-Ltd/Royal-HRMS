// Attendance "Export CSV": one day (the date shown in the table), a whole
// month, or a custom From–To range (one row per employee per day for month and
// range). The backend accepts exactly one of `date`, `month` or
// `from_date` + `to_date`, rejects future months / to-dates and ranges longer
// than MAX_EXPORT_RANGE_DAYS. `employeeId` (exact employee ID) narrows any of
// the three to one employee; the backend still applies the caller's scope.

export type AttendanceExportMode = "day" | "month" | "range";
export type AttendanceExportScope = "all" | "single";

export const MAX_EXPORT_RANGE_DAYS = 31;

export interface AttendanceExportInput {
  mode: AttendanceExportMode;
  date: string;      // YYYY-MM-DD
  month: string;     // YYYY-MM
  fromDate?: string; // YYYY-MM-DD
  toDate?: string;   // YYYY-MM-DD
  branch?: string;
  department?: string;
  employeeId?: string; // set → single-employee export
}

export function attendanceExportParams(input: AttendanceExportInput): Record<string, string> {
  const params: Record<string, string> =
    input.mode === "month" ? { month: input.month }
    : input.mode === "range" ? { from_date: input.fromDate ?? "", to_date: input.toDate ?? "" }
    : { date: input.date };
  // One employee: the branch / department filters on screen must not hide them.
  if (input.employeeId) {
    params.employee = input.employeeId;
    return params;
  }
  if (input.branch) params.branch = input.branch;
  if (input.department) params.department = input.department;
  return params;
}

export function attendanceExportFilename(input: AttendanceExportInput, branchSlug = ""): string {
  const period =
    input.mode === "month" ? input.month
    : input.mode === "range" ? `${input.fromDate}_to_${input.toDate}`
    : input.date;
  if (input.employeeId) return `attendance_${input.employeeId.replace(/[^A-Za-z0-9_-]/g, "_")}_${period}.csv`;
  return `attendance_${branchSlug}${period}.csv`;
}

/** Why a custom range can't be exported yet (shown under the pickers), or null when it's valid. */
export function exportRangeProblem(fromDate: string, toDate: string, today: string): string | null {
  if (!fromDate || !toDate) return "Select both From and To dates.";
  if (fromDate > toDate) return "From date must be on or before To date.";
  if (toDate > today) return "To date cannot be in the future.";
  const days = Math.round((Date.parse(toDate) - Date.parse(fromDate)) / 86_400_000) + 1;
  if (days > MAX_EXPORT_RANGE_DAYS) return `Range cannot exceed ${MAX_EXPORT_RANGE_DAYS} days.`;
  return null;
}
