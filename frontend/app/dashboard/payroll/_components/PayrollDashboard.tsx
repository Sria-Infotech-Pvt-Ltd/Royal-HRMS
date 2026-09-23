"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { PayrollCycle, PayrollSettings, EmployeeSalaryConfig } from "@/types/payroll";
import CancelCycleModal from "./CancelCycleModal";
import PayrollCalendarCard from "./PayrollCalendarCard";
import RecentPayrollRunsCard from "./RecentPayrollRunsCard";
import PendingCyclesCard from "./PendingCyclesCard";
import CancelledCyclesDetails from "./CancelledCyclesDetails";
import { MONTHS_LONG, type PagedResponse, cycleForMonth, PENDING_CYCLES_SECTION_ID } from "./payrollDashboardShared";

interface Props {
  onRunPayroll: (month?: string, year?: string) => void;
  onResumeCycle: (id: string, status: string, cycleStart?: string) => void;
  canResume: boolean;
  /** "Employees w/ Salary" KPI card jumps straight to the Salary Setup tab
      in one click, instead of making the user find and click the tab themselves. */
  onGoToSalarySetup?: () => void;
}

export default function PayrollDashboard({ onRunPayroll, onResumeCycle, canResume, onGoToSalarySetup }: Props) {
  const { data: cyclesPage, loading: cyclesLoading, refetch } =
    useFetch<PagedResponse<PayrollCycle>>(API.payroll.cycles);
  const { data: settings } = useFetch<PayrollSettings>(API.payroll.settings);
  const { data: salaryPage } =
    useFetch<PagedResponse<EmployeeSalaryConfig>>(API.payroll.employeeSalary);

  const [cancelTarget, setCancelTarget] = useState<PayrollCycle | null>(null);

  const cycles   = cyclesPage?.results ?? [];
  const empCount = salaryPage?.count ?? 0;
  const pending  = cycles.filter(c => !["paid","closed","cancelled"].includes(c.status));
  const paid     = cycles.filter(c =>  ["paid","closed"].includes(c.status));

  const now      = new Date();
  const nowYear  = now.getFullYear();
  const nowMonth = now.getMonth();
  const today    = now.getDate();
  const payDay   = settings?.pay_day ?? 30;

  // Calendar navigation state — defaults to current month
  const [calMonth, setCalMonth] = useState(nowMonth);
  const [calYear,  setCalYear]  = useState(nowYear);

  function prevMonth() {
    if (calMonth === 0) { setCalMonth(11); setCalYear(y => y - 1); }
    else                { setCalMonth(m => m - 1); }
  }
  function nextMonth() {
    if (calMonth === 11) { setCalMonth(0); setCalYear(y => y + 1); }
    else                 { setCalMonth(m => m + 1); }
  }

  // Missed months: only after first run, only past months (before current month)
  const missedMonths: { month: number; year: number }[] = (() => {
    if (cycles.length === 0) return [];
    const result: { month: number; year: number }[] = [];
    for (let m = 0; m < nowMonth; m++) {
      const exists = cycles.some(c => {
        if (c.status === "cancelled") return false;
        const start = new Date(c.cycle_start);
        const end   = new Date(c.cycle_end);
        const first = new Date(nowYear, m, 1);
        const last  = new Date(nowYear, m + 1, 0);
        return start <= last && end >= first;
      });
      if (!exists) result.push({ month: m, year: nowYear });
    }
    return result.reverse(); // most recent first
  })();

  const calMonthName  = MONTHS_LONG[calMonth];
  const calIsToday    = calMonth === nowMonth && calYear === nowYear;
  const calIsPast     = new Date(calYear, calMonth, 1) < new Date(nowYear, nowMonth, 1);
  const calIsFuture   = new Date(calYear, calMonth, 1) > new Date(nowYear, nowMonth, 1);
  const selectedCycle = cycleForMonth(cycles, calYear, calMonth);

  function scrollToPendingCycles() {
    document.getElementById(PENDING_CYCLES_SECTION_ID)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const STATS = [
    {
      label: "Employees w/ Salary", value: empCount > 0 ? String(empCount) : "—", sub: "CTC configured", icon: "ti-users", cls: "si-primary",
      onClick: onGoToSalarySetup, title: "Go to Salary Setup",
    },
    {
      label: "Pending Cycles", value: String(pending.length), sub: pending.length > 0 ? `${pending.length} need action` : "All up to date", icon: "ti-clock", cls: pending.length > 0 ? "si-warn" : "si-success",
      onClick: pending.length > 0 ? scrollToPendingCycles : undefined,
      title: pending.length > 0 ? "Jump to pending cycles" : undefined,
    },
    { label: "Paid This Year",       value: String(paid.length),                   sub: "Completed payroll runs",  icon: "ti-circle-check",  cls: "si-success"  },
    { label: "Next Pay Day",         value: payDay ? `${payDay} ${MONTHS_LONG[nowMonth]}` : "—", sub: settings ? `Cycle ${settings.cycle_start_day}–${settings.cycle_end_day}` : "Not configured", icon: "ti-calendar-event", cls: "si-info" },
    { label: "Total Payroll Runs",   value: String(cycles.length),                 sub: "All time",                icon: "ti-history",       cls: "si-primary"  },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* Stats row */}
      <div className="stats-grid" style={{ marginBottom: 0 }}>
        {STATS.map(s => (
          <div
            key={s.label}
            className="stat-card"
            role={s.onClick ? "button" : undefined}
            tabIndex={s.onClick ? 0 : undefined}
            onClick={s.onClick}
            title={s.title}
            style={s.onClick ? { cursor: "pointer" } : undefined}
          >
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 8 }}>
              <div>
                <div className="stat-label">{s.label}</div>
                <div className="stat-value" style={{ fontSize: 22 }}>{s.value}</div>
                <div className="stat-sub">{s.sub}</div>
              </div>
              <div className={`stat-icon ${s.cls}`} style={{ float: "none", margin: 0 }}>
                <i className={`ti ${s.icon}`} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Calendar + Recent runs */}
      <div className="payroll-calendar-row" style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: 16 }}>
        <PayrollCalendarCard
          calMonth={calMonth}
          calYear={calYear}
          calMonthName={calMonthName}
          calIsToday={calIsToday}
          calIsPast={calIsPast}
          calIsFuture={calIsFuture}
          today={today}
          payDay={payDay}
          missedMonths={missedMonths}
          selectedCycle={selectedCycle}
          canResume={canResume}
          prevMonth={prevMonth}
          nextMonth={nextMonth}
          onSelectMissedMonth={(m, y) => { setCalMonth(m); setCalYear(y); }}
          onResumeCycle={onResumeCycle}
          onRunPayroll={onRunPayroll}
        />

        <RecentPayrollRunsCard
          cycles={cycles}
          cyclesLoading={cyclesLoading}
          canResume={canResume}
          onRunPayroll={onRunPayroll}
          onResumeCycle={onResumeCycle}
        />
      </div>

      {/* Pending cycles — action required */}
      {pending.length > 0 && (
        <PendingCyclesCard
          pending={pending}
          canResume={canResume}
          onResumeCycle={onResumeCycle}
          onCancelCycle={setCancelTarget}
        />
      )}

      {/* Cancelled cycles — audit trail */}
      {cycles.some(c => c.status === "cancelled") && (
        <CancelledCyclesDetails cycles={cycles} />
      )}

      {/* Salary setup reminder */}
      {empCount === 0 && !cyclesLoading && (
        <div className="alert alert-warn">
          <i className="ti ti-alert-triangle" />
          <span>No employee CTC has been configured. Go to <strong>Salary Setup</strong> tab to assign CTC before running payroll.</span>
        </div>
      )}

      {cancelTarget && (
        <CancelCycleModal
          cycle={cancelTarget}
          onCancelled={() => { setCancelTarget(null); refetch(); }}
          onClose={() => setCancelTarget(null)}
        />
      )}

      <style jsx>{`
        @media (max-width: 768px) {
          .payroll-calendar-row {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
}
