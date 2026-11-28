// The two summaries the "Perform an action" modal shows: what the chosen action changes (BEFORE → AFTER) and the employee's
// details it leaves alone.

import { tr } from "@/lib/i18n/tr";
import { formatRecordDate } from "@/lib/performAction";
import { directoryStatusLabel, reportingManagerDisplay, type Employee, type FieldOption } from "@/app/dashboard/employees/_data";
import type {
  ActionHistoryRow, EmployeeDetailSnapshot, FieldDiffRow,
} from "@/app/dashboard/employees/_components/PerformActionFields/types";
import type { PerformActionValues } from "@/hooks/usePerformActionForm";

export interface PerformActionOptionLists {
  positionOptions: FieldOption[];
  moveUnitOptions: FieldOption[];
  movePositionOptions: FieldOption[];
  managerOptions: FieldOption[];
}

export interface PerformActionContext {
  employee: Employee;
  detail: EmployeeDetailSnapshot | null;
  currentRecord: ActionHistoryRow | null;
  currentStatusLabel: string;
  currentManagerName: string | null;
}

const labelOf = (options: FieldOption[], value: string) => options.find(option => option.value === value)?.label ?? null;
const rupees = (amount: string) => `₹${Number(amount).toLocaleString("en-IN")}`;

/** The fields the chosen action may change; the "not changed" list leaves these out. */
export function changedFieldKeys(values: PerformActionValues): string[] {
  switch (values.actionType) {
    case "promotion": return ["position"];
    case "org_assignment": return ["reporting_manager", "work_location", ...(values.moveUnitId ? ["org_unit", "position"] : [])];
    case "pay_change": return ["annual_ctc"];
    case "confirmation": return ["employment_status"];
    case "separation": return ["employment_status", "last_working_day"];
    default: return [];
  }
}

function orgAssignmentRows(values: PerformActionValues, options: PerformActionOptionLists, context: PerformActionContext): FieldDiffRow[] {
  const { employee, detail, currentManagerName } = context;
  const rows: FieldDiffRow[] = [];
  if (values.moveUnitId) {
    rows.push({ key: "org_unit", label: tr("Org unit"), before: employee.orgUnitName || employee.department || "—", after: labelOf(options.moveUnitOptions, values.moveUnitId) });
    rows.push({ key: "position", label: tr("Position"), before: employee.designation || "—", after: labelOf(options.movePositionOptions, values.positionId) });
  }
  rows.push({ key: "reporting_manager", label: tr("Reporting manager"), before: reportingManagerDisplay(currentManagerName, employee.noManagerByDesign), after: labelOf(options.managerOptions, values.managerId) });
  rows.push({ key: "work_location", label: tr("Work location"), before: detail?.work_location || "—", after: values.workLocation || null });
  return rows;
}

/** BEFORE → AFTER rows for the chosen action; `after` is null while the field is still unchosen. */
export function buildDiffRows(values: PerformActionValues, options: PerformActionOptionLists, context: PerformActionContext): FieldDiffRow[] {
  const { annualCtc, effectiveFrom, lastWorkingDay } = values;
  switch (values.actionType) {
    case "promotion": {
      const rows: FieldDiffRow[] = [{ key: "position", label: tr("Position"), before: context.employee.designation || "—", after: labelOf(options.positionOptions, values.positionId) }];
      if (annualCtc) rows.push({ key: "annual_ctc", label: tr("Annual CTC"), before: "—", after: rupees(annualCtc) });
      return rows;
    }
    case "org_assignment": return orgAssignmentRows(values, options, context);
    case "pay_change": return [{ key: "annual_ctc", label: tr("Annual CTC"), before: "—", after: annualCtc ? rupees(annualCtc) : null }];
    case "confirmation": return [{ key: "employment_status", label: tr("Employee status"), before: tr(context.currentStatusLabel), after: tr("Confirmed") }];
    case "separation": return [
      { key: "employment_status", label: tr("Employee status"), before: tr("Active"), after: tr("Notice Period") },
      { key: "notice_period_start", label: tr("Notice period starts"), before: tr("Not set"), after: effectiveFrom ? formatRecordDate(effectiveFrom) : null },
      { key: "last_working_day", label: tr("Last working day"), before: tr("Not set"), after: lastWorkingDay ? formatRecordDate(lastWorkingDay) : null },
    ];
    default: return [];
  }
}

/** The employee's details the chosen action does not change (all of them before an action is chosen). */
export function buildNotChangedRows(values: PerformActionValues, context: PerformActionContext): { label: string; value: string }[] {
  const { employee, detail, currentRecord, currentManagerName } = context;
  const orgUnitLabel = employee.orgUnitName
    ? (employee.orgUnitParentName ? `${employee.orgUnitName} › ${employee.orgUnitParentName}` : employee.orgUnitName)
    : (employee.department || "—");
  const changed = changedFieldKeys(values);
  const rows = [
    { key: "position", label: tr("Position"), value: employee.designation || "—" },
    { key: "org_unit", label: tr("Org unit"), value: orgUnitLabel },
    { key: "work_location", label: tr("Work location"), value: detail?.work_location || employee.location || "—" },
    { key: "reporting_manager", label: tr("Reporting manager"), value: reportingManagerDisplay(currentManagerName, employee.noManagerByDesign) },
    { key: "employment_status", label: tr("Status"), value: tr(directoryStatusLabel(employee)) },
    { key: "record_range", label: tr("Current record"), value: currentRecord ? `${formatRecordDate(currentRecord.effective_from)} → ${formatRecordDate(currentRecord.effective_to)}` : "—" },
  ];
  return rows
    .filter(row => row.key === "record_range" || (row.key === "position" && values.actionType !== "org_assignment") || !changed.includes(row.key))
    .map(row => ({ label: row.label, value: row.value }));
}
