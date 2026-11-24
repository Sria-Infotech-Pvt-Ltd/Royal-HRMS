"use client";

import type { CSSProperties } from "react";
import { useT } from "@/hooks/useI18n";
import type { EmployeeRow } from "./EmployeeAttendanceRow";

/** Whole-team numbers for the cycle, added up from the per-employee rows already on screen. */
export default function AttendanceTotals({ employees }: { employees: EmployeeRow[] }) {
  const t = useT();
  const sum = (pick: (row: EmployeeRow) => number) => employees.reduce((total, row) => total + pick(row), 0);
  const lopDays = sum(row => row.lop_days);
  const absentDays = sum(row => row.absent_days);
  const tiles = [
    { label: "Employees",   value: employees.length,                          icon: "ti-users",         accent: "var(--brand)" },
    { label: "Present days", value: sum(row => row.present_days),             icon: "ti-circle-check",  accent: "#16a34a" },
    { label: "Late",         value: sum(row => row.late_days),                icon: "ti-clock-exclamation", accent: "#d97706" },
    { label: "Absent",       value: absentDays,                               icon: "ti-user-off",      accent: "#dc2626", isAlert: absentDays > 0 },
    { label: "LOP days",     value: lopDays,                                  icon: "ti-coin-off",      accent: "#ea580c", isAlert: lopDays > 0 },
    { label: "Hours worked", value: Math.round(sum(row => row.working_hours)), icon: "ti-hourglass",    accent: "#0ea5e9" },
  ];
  return (
    <div className="aa-totals">
      {tiles.map(tile => (
        <div key={tile.label} className={`aa-total${tile.isAlert ? " is-alert" : ""}`} style={{ "--aa-accent": tile.accent } as CSSProperties}>
          <span className="aa-total-icon"><i className={`ti ${tile.icon}`} /></span>
          <div><b>{tile.value}</b><span>{t(tile.label)}</span></div>
        </div>
      ))}
    </div>
  );
}
