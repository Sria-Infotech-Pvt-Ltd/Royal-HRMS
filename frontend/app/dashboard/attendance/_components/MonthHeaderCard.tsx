"use client";

// The toolbar above an employee's month. Left: the employee (avatar, searchable dropdown, previous / next employee, and chips for ID,
// designation and department). Right, once someone is chosen: the month controls and the Calendar / List switch.

import SearchableSelect from "@/components/SearchableSelect";
import { PALETTE, tint } from "./attendancePalette";
import { formatMonthLabel, type EmployeeOption } from "./monthView";

export type MonthViewMode = "calendar" | "list";

interface Props {
  employees: EmployeeOption[];
  /** The chosen employee, or null before one is picked. */
  employee: EmployeeOption | null;
  onSelectEmployee: (employeeId: string) => void;
  /** Null when there is no previous / next employee in the list. */
  onPreviousEmployee: (() => void) | null;
  onNextEmployee: (() => void) | null;
  month: string;
  canGoNextMonth: boolean;
  isCurrentMonth: boolean;
  onMonthStep: (delta: number) => void;
  onThisMonth: () => void;
  view: MonthViewMode;
  onViewChange: (view: MonthViewMode) => void;
}

const initialsOf = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map(word => word[0].toUpperCase()).join("") || "?";

function Chip({ icon, children }: { icon: string; children: React.ReactNode }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12, fontWeight: 600, padding: "3px 10px", borderRadius: 999, background: tint(PALETTE.brand, 0.08), color: "var(--on-bg)", border: `1px solid ${tint(PALETTE.brand, 0.18)}` }}>
      <i className={`ti ${icon}`} aria-hidden="true" style={{ color: PALETTE.brand, fontSize: 13 }} />{children}
    </span>
  );
}

export default function MonthHeaderCard({
  employees, employee, onSelectEmployee, onPreviousEmployee, onNextEmployee, month, canGoNextMonth, isCurrentMonth, onMonthStep, onThisMonth, view, onViewChange,
}: Props) {
  const options = employees.map(option => ({ value: option.id, label: `${option.full_name} (${option.employee_id})` }));
  return (
    <div className="card" style={{ padding: "14px 18px", display: "flex", flexWrap: "wrap", gap: 16, alignItems: "center", background: `linear-gradient(135deg, ${tint(PALETTE.brand, 0.07)} 0%, var(--surface) 55%)` }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, flex: "1 1 420px", minWidth: 0 }}>
        <div aria-hidden="true" style={{ width: 52, height: 52, borderRadius: "50%", flexShrink: 0, display: "grid", placeItems: "center", fontWeight: 800, fontSize: 17, color: "#fff", background: employee ? `linear-gradient(135deg, ${PALETTE.brand}, #A78BFA)` : "var(--outline-v)", boxShadow: employee ? `0 4px 12px ${tint(PALETTE.brand, 0.35)}` : "none" }}>
          {employee ? initialsOf(employee.full_name) : <i className="ti ti-user" style={{ color: "var(--outline)", fontSize: 22 }} />}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            <div style={{ width: 300, maxWidth: "100%" }}>
              <SearchableSelect
                value={employee?.id ?? ""} onChange={onSelectEmployee} options={options} inputClassName="field-input"
                placeholder="Select an employee" searchPlaceholder="Search by name or ID…"
              />
            </div>
            {employee && (
              <div style={{ display: "flex", gap: 4 }}>
                <button className="btn btn-ghost btn-sm" disabled={!onPreviousEmployee} onClick={() => onPreviousEmployee?.()} aria-label="Previous employee" title="Previous employee"><i className="ti ti-user-up" /></button>
                <button className="btn btn-ghost btn-sm" disabled={!onNextEmployee} onClick={() => onNextEmployee?.()} aria-label="Next employee" title="Next employee"><i className="ti ti-user-down" /></button>
              </div>
            )}
          </div>
          {employee && (
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
              <Chip icon="ti-id-badge-2">{employee.employee_id}</Chip>
              {employee.designation && <Chip icon="ti-briefcase">{employee.designation}</Chip>}
              {employee.department && <Chip icon="ti-building">{employee.department}</Chip>}
            </div>
          )}
        </div>
      </div>

      {employee && (
        <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => onMonthStep(-1)} aria-label="Previous month"><i className="ti ti-chevron-left" /></button>
            <span aria-live="polite" style={{ fontWeight: 700, fontSize: 15, minWidth: 130, textAlign: "center", color: "var(--on-bg)" }}>{formatMonthLabel(month)}</span>
            <button className="btn btn-ghost btn-sm" onClick={() => onMonthStep(1)} disabled={!canGoNextMonth} aria-label="Next month"><i className="ti ti-chevron-right" /></button>
            {!isCurrentMonth && <button className="btn btn-ghost btn-sm" onClick={onThisMonth}>This month</button>}
          </div>
          <div role="group" aria-label="View" style={{ display: "inline-flex", padding: 3, borderRadius: 999, background: "var(--bg-low)", border: "1px solid var(--outline-v)" }}>
            {(["calendar", "list"] as const).map(mode => (
              <button
                key={mode} type="button" aria-pressed={view === mode} onClick={() => onViewChange(mode)}
                style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 15px", borderRadius: 999, border: 0, cursor: "pointer", fontSize: 12.5, fontWeight: 700, transition: "all .15s", background: view === mode ? PALETTE.brand : "transparent", color: view === mode ? "#fff" : "var(--on-variant)", boxShadow: view === mode ? `0 2px 8px ${tint(PALETTE.brand, 0.35)}` : "none" }}
              >
                <i className={`ti ${mode === "calendar" ? "ti-calendar" : "ti-list"}`} aria-hidden="true" />{mode === "calendar" ? "Calendar" : "List"}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
