// Shared CSV-export logic for employee-list snapshots — used by the
// Employee Directory's own filtered "Export" button (hooks/useEmployees.tsx)
// and the admin dashboard's "Export report" button (an unfiltered, full
// workforce snapshot). Extracted here so both produce byte-identical column
// layouts instead of two independently-maintained CSV builders drifting apart.
import type { ApiEmployee } from "@/app/dashboard/employees/_data";

/** Same row-status precedence StatusBadge/EmployeeTableRow render, applied to
 * the raw list-API shape so the exported CSV's Status column reads the same
 * human label the table shows instead of the raw backend value. */
export function exportStatusLabel(r: ApiEmployee): string {
  const onNotice = r.status === "active" && !!r.last_working_day;
  if (onNotice) return "Notice Period";
  if (r.status === "active") return "Active";
  if (r.status === "onboarding") return "Onboarding";
  if (r.status === "probation") return "Probation";
  return "Exited";
}

export function employeesToCsv(rows: ApiEmployee[]): string {
  const headers = [
    "Employee ID", "Name", "Email", "Phone", "Department", "Designation", "Branch",
    "Role", "Date of Joining", "Status", "Reporting Manager", "Org Unit",
  ];
  const csvRows = rows.map(r => [
    r.employee_id, r.full_name, r.email, r.phone,
    // The legacy `department` string is blank for anyone hired onto a real
    // Position (see apiToEmployee's own comment) — derive it the same way
    // the table row does (org_unit_name first, falling back to the legacy
    // field) instead of the always-blank legacy field alone.
    r.org_unit_name || r.department || "",
    r.designation, r.branch, r.role_display, r.date_of_joining,
    exportStatusLabel(r),
    r.reporting_manager?.name ?? "",
    r.org_unit_name ?? "",
  ]);
  const escape = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  return [headers, ...csvRows].map(row => row.map(escape).join(",")).join("\r\n");
}

export function downloadCsv(csv: string, filename: string): void {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
