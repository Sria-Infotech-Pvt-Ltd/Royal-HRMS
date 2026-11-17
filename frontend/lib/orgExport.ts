import type { OrgUnit, Position } from "@/types/orgStructure";

const EXCEL_BYTE_ORDER_MARK = String.fromCharCode(0xfeff);
const HEADERS = ["Org unit", "Unit path", "Position", "Grade", "Head of unit", "Status", "Holder", "Employee ID", "Branch", "Reports to"];

/** One CSV cell. A value a spreadsheet would run as a formula (starts with = + - @) is made plain text first. */
export function csvCell(value: string): string {
  const safe = /^[=+\-@\t\r]/.test(value) ? `'${value}` : value;
  return /[",\n\r]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
}

function unitPath(unit: OrgUnit | undefined, byId: Map<string, OrgUnit>): string {
  const names: string[] = [];
  const seen = new Set<string>();
  let current = unit;
  while (current && !seen.has(current.id)) {
    seen.add(current.id);
    names.unshift(current.name);
    current = current.parent ? byId.get(current.parent) : undefined;
  }
  return names.join(" > ");
}

function statusOf(position: Position): string {
  if (!position.is_active) return "Inactive";
  return position.holder ? "Filled" : "Vacant";
}

/** Every position with where it sits, who holds it and who it reports to, ready to open in Excel. */
export function buildPositionsCsv(units: OrgUnit[], positions: Position[]): string {
  const byId = new Map(units.map(unit => [unit.id, unit]));
  const rows = positions.map(position => {
    const unit = byId.get(position.org_unit);
    return [
      unit?.name ?? position.org_unit_name, unitPath(unit, byId), position.title, position.grade,
      position.is_chief ? "Yes" : "", statusOf(position), position.holder_name ?? "", position.holder_employee_id ?? "",
      position.branch_name ?? "", position.reports_to?.title ?? "",
    ];
  });
  rows.sort((first, second) => first[1].localeCompare(second[1]) || first[2].localeCompare(second[2]));
  return [HEADERS, ...rows].map(row => row.map(csvCell).join(",")).join("\r\n");
}

/** Saves text as a file in the browser. A leading byte-order mark makes Excel read accented names correctly. */
export function downloadTextFile(fileName: string, text: string, type = "text/csv;charset=utf-8"): void {
  const url = URL.createObjectURL(new Blob([EXCEL_BYTE_ORDER_MARK, text], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
