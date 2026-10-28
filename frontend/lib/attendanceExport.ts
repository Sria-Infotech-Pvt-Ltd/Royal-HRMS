// Attendance "Export CSV": one day (the date shown in the table) or a whole
// month (one row per employee per day). The backend accepts either `date` or
// `month`, never both, and rejects future months.

export type AttendanceExportMode = "day" | "month";

export interface AttendanceExportInput {
  mode: AttendanceExportMode;
  date: string;   // YYYY-MM-DD
  month: string;  // YYYY-MM
  branch?: string;
  department?: string;
}

export function attendanceExportParams(input: AttendanceExportInput): Record<string, string> {
  const params: Record<string, string> =
    input.mode === "month" ? { month: input.month } : { date: input.date };
  if (input.branch) params.branch = input.branch;
  if (input.department) params.department = input.department;
  return params;
}

export function attendanceExportFilename(input: AttendanceExportInput, branchSlug = ""): string {
  return `attendance_${branchSlug}${input.mode === "month" ? input.month : input.date}.csv`;
}
