"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { PayrollCycle, PayrollSettings, EmployeeSalaryConfig } from "@/types/payroll";
import CancelCycleModal from "./CancelCycleModal";

const MONTHS_LONG = [
  "January","February","March","April","May","June",
  "July","August","September","October","November","December",
];
const MONTHS_SHORT = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

interface Props {
  onRunPayroll: (month?: string, year?: string) => void;
  onResumeCycle: (id: string, status: string) => void;
  canResume: boolean;
}
interface PagedResponse<T> { results: T[]; count: number; }

const STATUS_BADGE: Record<string, string> = {
  paid:                "badge badge-success",
  closed:              "badge badge-success",
  cancelled:           "badge badge-error",
  draft:               "badge badge-neutral",
  attendance_pending:  "badge badge-warn",
  attendance_approved: "badge badge-info",
  processing:          "badge badge-info",
  payslips_generated:  "badge badge-primary",
  query_window_open:   "badge badge-info",
};

const STATUS_LABEL: Record<string, string> = {
  paid:                "Paid",
  closed:              "Closed",
  cancelled:           "Cancelled",
  draft:               "Draft",
  attendance_pending:  "Awaiting Approval",
  attendance_approved: "Approved",
  processing:          "Processing",
  payslips_generated:  "Payslips Ready",
  query_window_open:   "Query Window",
};

const UNCANCELLABLE = ["paid", "closed", "cancelled"];
const DAYS_LABEL    = ["S","M","T","W","T","F","S"];

function getCalendarDates(year: number, month: number) {
  return {
    firstDay: new Date(year, month, 1).getDay(),
    days:     new Date(year, month + 1, 0).getDate(),
  };
}

/** Returns the cycle (non-cancelled) whose period covers the given month/year, or null. */
function cycleForMonth(cycles: PayrollCycle[], calYear: number, calMonth: number): PayrollCycle | null {
  return cycles.find(c => {
    if (c.status === "cancelled") return false;
    const start = new Date(c.cycle_start);
    const end   = new Date(c.cycle_end);
    // Cycle covers calMonth if its date range overlaps with [first, last] of calMonth
    const first = new Date(calYear, calMonth, 1);
    const last  = new Date(calYear, calMonth + 1, 0);
    return start <= last && end >= first;
  }) ?? null;
}

const DETAIL_STATUSES   = new Set(["paid", "closed"]);
const TERMINAL_STATUSES = new Set(["paid", "closed", "cancelled"]);

export default function PayrollDashboard({ onRunPayroll, onResumeCycle, canResume }: Props) {
  const router = useRouter();
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

  const { firstDay, days } = getCalendarDates(calYear, calMonth);
  const calDates = Array.from({ length: days }, (_, i) => i + 1);

  const STATS = [
    { label: "Employees w/ Salary", value: empCount > 0 ? String(empCount) : "—", sub: "CTC configured",          icon: "ti-users",         cls: "si-primary" },
    { label: "Pending Cycles",       value: String(pending.length),                sub: pending.length > 0 ? `${pending.length} need action` : "All up to date", icon: "ti-clock", cls: pending.length > 0 ? "si-warn" : "si-success" },
    { label: "Paid This Year",       value: String(paid.length),                   sub: "Completed payroll runs",  icon: "ti-circle-check",  cls: "si-success"  },
    { label: "Next Pay Day",         value: payDay ? `${payDay} ${MONTHS_LONG[nowMonth]}` : "—", sub: settings ? `Cycle ${settings.cycle_start_day}–${settings.cycle_end_day}` : "Not configured", icon: "ti-calendar-event", cls: "si-info" },
    { label: "Total Payroll Runs",   value: String(cycles.length),                 sub: "All time",                icon: "ti-history",       cls: "si-primary"  },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* Stats row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 16 }}>
        {STATS.map(s => (
          <div key={s.label} className="stat-card">
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
      <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: 16 }}>

        {/* Payroll Calendar */}
        <div className="card">

          {/* Header with prev/next navigation */}
          <div className="card-header" style={{ paddingBottom: 8 }}>
            <div className="card-title" style={{ fontSize: 13 }}>
              <i className="ti ti-calendar-event" /> Payroll Calendar
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <button className="btn btn-ghost btn-sm" style={{ padding: "2px 6px" }} onClick={prevMonth}>
                <i className="ti ti-chevron-left" />
              </button>
              <span style={{ fontSize: 12, fontWeight: 600, minWidth: 100, textAlign: "center" }}>
                {calMonthName} {calYear}
              </span>
              <button className="btn btn-ghost btn-sm" style={{ padding: "2px 6px" }} onClick={nextMonth}>
                <i className="ti ti-chevron-right" />
              </button>
            </div>
          </div>

          <div className="card-body" style={{ padding: "8px 16px 16px" }}>

            {/* Missed month filter chips — shown only when cycles exist */}
            {missedMonths.length > 0 && (
              <div style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: "var(--warn)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 5 }}>
                  Missing payroll
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {missedMonths.map(({ month: m, year: y }) => {
                    const isSelected = calMonth === m && calYear === y;
                    return (
                      <button
                        key={`${y}-${m}`}
                        onClick={() => { setCalMonth(m); setCalYear(y); }}
                        style={{
                          fontSize: 11, fontWeight: 600,
                          padding: "2px 8px", borderRadius: 20,
                          border: isSelected ? "1.5px solid var(--warn)" : "1.5px solid var(--outline-v)",
                          background: isSelected ? "rgba(var(--warn-rgb, 234,179,8), 0.12)" : "transparent",
                          color: isSelected ? "var(--warn)" : "var(--on-variant)",
                          cursor: "pointer",
                        }}
                      >
                        {MONTHS_SHORT[m]}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Calendar grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 2, marginBottom: 8 }}>
              {DAYS_LABEL.map((d, i) => (
                <div key={i} style={{ textAlign: "center", fontSize: 10, fontWeight: 600, color: "var(--on-variant)", padding: "4px 0" }}>{d}</div>
              ))}
              {Array.from({ length: firstDay }).map((_, i) => <div key={`e${i}`} />)}
              {calDates.map(d => {
                const isPayDay = d === payDay;
                const isToday  = calIsToday && d === today;
                return (
                  <div
                    key={d}
                    style={{
                      textAlign: "center", fontSize: 11, padding: "4px 2px",
                      borderRadius: 6, fontWeight: isToday ? 700 : 400,
                      background: isPayDay ? "var(--primary)" : "transparent",
                      color:      isPayDay ? "#fff" : "var(--on-bg)",
                      border:     isToday && !isPayDay ? "1.5px solid var(--primary)" : "none",
                      opacity:    calIsPast || calIsFuture ? 0.7 : 1,
                    }}
                  >
                    {d}
                  </div>
                );
              })}
            </div>

            {/* Legend */}
            <div style={{ display: "flex", flexDirection: "column", gap: 5, borderTop: "1px solid var(--outline-v)", paddingTop: 10 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11 }}>
                <div style={{ width: 10, height: 10, borderRadius: 2, background: "var(--primary)" }} />
                <span>Pay Day — {payDay} {calMonthName}</span>
              </div>
              {calIsToday && (
                <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11 }}>
                  <div style={{ width: 10, height: 10, borderRadius: 2, border: "2px solid var(--primary)" }} />
                  <span>Today — {today} {calMonthName}</span>
                </div>
              )}
            </div>

            {/* Payroll status for selected month */}
            <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--outline-v)" }}>
              {selectedCycle ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Payroll status</span>
                    <span className={STATUS_BADGE[selectedCycle.status] ?? "badge badge-neutral"}>
                      {STATUS_LABEL[selectedCycle.status] ?? selectedCycle.status}
                    </span>
                  </div>
                  {canResume && !["paid","closed"].includes(selectedCycle.status) && (
                    <button
                      className="btn btn-ghost btn-sm"
                      style={{ width: "100%", justifyContent: "center" }}
                      onClick={() => onResumeCycle(selectedCycle.id, selectedCycle.status)}
                    >
                      <i className="ti ti-arrow-right" /> Resume {calMonthName}
                    </button>
                  )}
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ fontSize: 12, color: calIsPast ? "var(--warn)" : "var(--on-variant)", display: "flex", alignItems: "center", gap: 6 }}>
                    {calIsPast
                      ? <><i className="ti ti-alert-triangle" style={{ color: "var(--warn)" }} /> No payroll run</>
                      : calIsFuture
                      ? <><i className="ti ti-clock" /> Future month</>
                      : <><i className="ti ti-player-play" /> Ready to run</>
                    }
                  </div>
                  {canResume && !calIsFuture && (
                    <button
                      className="btn btn-filled btn-sm"
                      style={{ width: "100%", justifyContent: "center" }}
                      onClick={() => onRunPayroll(calMonthName, String(calYear))}
                    >
                      <i className="ti ti-player-play" /> Run {calMonthName} Payroll
                    </button>
                  )}
                </div>
              )}
            </div>

          </div>
        </div>

        {/* Recent Payroll Runs */}
        <div className="card">
          <div className="card-header">
            <div className="card-title"><i className="ti ti-history" /> Recent Payroll Runs</div>
          </div>

          {cyclesLoading ? (
            <div style={{ padding: "40px", textAlign: "center", color: "var(--on-variant)" }}>
              <i className="ti ti-loader-2 animate-spin" style={{ fontSize: 24 }} />
              <div style={{ marginTop: 8, fontSize: 13 }}>Loading payroll cycles…</div>
            </div>
          ) : cycles.length === 0 ? (
            <div style={{ padding: "40px", textAlign: "center", color: "var(--on-variant)" }}>
              <i className="ti ti-calendar-off" style={{ fontSize: 36, display: "block", marginBottom: 12 }} />
              <div style={{ fontWeight: 600, marginBottom: 4 }}>No payroll runs yet</div>
              <div style={{ fontSize: 13, marginBottom: 16 }}>Click "Run Payroll" to start your first payroll cycle.</div>
              <button className="btn btn-filled btn-sm" onClick={() => onRunPayroll()}>
                <i className="ti ti-player-play" /> Run First Payroll
              </button>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Period</th>
                    <th>Cycle Start</th>
                    <th>Cycle End</th>
                    <th>Pay Date</th>
                    <th>Payslips</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {cycles.map(c => {
                    const isDetail   = DETAIL_STATUSES.has(c.status);
                    const isTerminal = TERMINAL_STATUSES.has(c.status);
                    const handleClick = isDetail
                      ? () => router.push(`/dashboard/payroll/runs/${c.id}`)
                      : !isTerminal && canResume ? () => onResumeCycle(c.id, c.status) : undefined;
                    return (
                    <tr key={c.id} style={{ cursor: handleClick ? "pointer" : "default" }} onClick={handleClick}>
                      <td style={{ fontWeight: 600, fontSize: 13 }}>
                        {new Date(c.cycle_start).toLocaleString("en-IN", { month: "long", year: "numeric" })}
                      </td>
                      <td style={{ fontSize: 13 }}>{c.cycle_start}</td>
                      <td style={{ fontSize: 13 }}>{c.cycle_end}</td>
                      <td style={{ fontSize: 13, fontWeight: 500 }}>{c.pay_date}</td>
                      <td>
                        <span style={{ fontWeight: 600 }}>{c.payslip_count}</span>
                        <span style={{ color: "var(--on-variant)", fontSize: 12 }}> employees</span>
                      </td>
                      <td>
                        <span className={STATUS_BADGE[c.status] ?? "badge badge-neutral"}>
                          {STATUS_LABEL[c.status] ?? c.status}
                        </span>
                      </td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Pending cycles — action required */}
      {pending.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <i className="ti ti-alert-circle" style={{ color: "var(--warn)" }} />
              {" "}Action Required — {pending.length} Pending Cycle{pending.length !== 1 ? "s" : ""}
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Period</th><th>Pay Date</th><th>Status</th>
                  <th>L1 Approver</th><th>Payslips</th><th />
                </tr>
              </thead>
              <tbody>
                {pending.map(c => (
                  <tr key={c.id} style={{ cursor: canResume ? "pointer" : "default" }} onClick={canResume ? () => onResumeCycle(c.id, c.status) : undefined}>
                    <td style={{ fontWeight: 600 }}>
                      {new Date(c.cycle_start).toLocaleString("en-IN", { month: "long", year: "numeric" })}
                    </td>
                    <td>{c.pay_date}</td>
                    <td><span className={STATUS_BADGE[c.status] ?? "badge badge-neutral"}>{STATUS_LABEL[c.status] ?? c.status}</span></td>
                    <td style={{ fontSize: 13, color: "var(--on-variant)" }}>{c.l1_approver_name ?? "—"}</td>
                    <td>{c.payslip_count}</td>
                    <td onClick={e => e.stopPropagation()}>
                      {!UNCANCELLABLE.includes(c.status) && (
                        <button className="btn btn-ghost btn-sm" style={{ color: "var(--error)", fontSize: 12 }} onClick={() => setCancelTarget(c)} title="Cancel this cycle">
                          <i className="ti ti-ban" /> Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Cancelled cycles — audit trail */}
      {cycles.some(c => c.status === "cancelled") && (
        <details className="card" style={{ padding: 0 }}>
          <summary style={{ padding: "12px 16px", cursor: "pointer", fontWeight: 600, fontSize: 13, listStyle: "none", display: "flex", alignItems: "center", gap: 8 }}>
            <i className="ti ti-ban" style={{ color: "var(--error)" }} />
            Cancelled Cycles ({cycles.filter(c => c.status === "cancelled").length})
          </summary>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Period</th><th>Cancelled By</th><th>Cancelled At</th><th>Reason</th></tr></thead>
              <tbody>
                {cycles.filter(c => c.status === "cancelled").map(c => (
                  <tr key={c.id}>
                    <td style={{ fontWeight: 600, fontSize: 13 }}>
                      {new Date(c.cycle_start).toLocaleString("en-IN", { month: "long", year: "numeric" })}
                    </td>
                    <td style={{ fontSize: 13 }}>{c.cancelled_by_name ?? "—"}</td>
                    <td style={{ fontSize: 13, color: "var(--on-variant)" }}>
                      {c.cancelled_at ? new Date(c.cancelled_at).toLocaleDateString("en-IN") : "—"}
                    </td>
                    <td style={{ fontSize: 13, color: "var(--on-variant)", maxWidth: 300 }}>{c.cancellation_reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
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
    </div>
  );
}
