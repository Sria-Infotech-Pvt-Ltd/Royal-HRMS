"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { PayrollCycle, PayrollSettings, EmployeeSalaryConfig } from "@/types/payroll";
import CancelCycleModal from "./CancelCycleModal";

interface Props {
  onRunPayroll: () => void;
  onResumeCycle: (id: string, status: string) => void;
  canResume: boolean;
}
interface PagedResponse<T> { results: T[]; count: number; }

const STATUS_BADGE: Record<string, string> = {
  paid:                 "badge badge-success",
  closed:               "badge badge-success",
  cancelled:            "badge badge-error",
  draft:                "badge badge-neutral",
  attendance_pending:   "badge badge-warn",
  attendance_approved:  "badge badge-info",
  processing:           "badge badge-info",
  payslips_generated:   "badge badge-primary",
  query_window_open:    "badge badge-info",
};

const STATUS_LABEL: Record<string, string> = {
  paid:                 "Paid",
  closed:               "Closed",
  cancelled:            "Cancelled",
  draft:                "Draft",
  attendance_pending:   "Awaiting Approval",
  attendance_approved:  "Approved",
  processing:           "Processing",
  payslips_generated:   "Payslips Ready",
  query_window_open:    "Query Window",
};

const UNCANCELLABLE = ["paid", "closed", "cancelled"];

const DAYS_LABEL = ["S", "M", "T", "W", "T", "F", "S"];

function getCalendarDates(year: number, month: number) {
  const firstDay = new Date(year, month, 1).getDay();
  const days     = new Date(year, month + 1, 0).getDate();
  return { firstDay, days };
}

export default function PayrollDashboard({ onRunPayroll, onResumeCycle, canResume }: Props) {
  const { data: cyclesPage, loading: cyclesLoading, refetch } =
    useFetch<PagedResponse<PayrollCycle>>(API.payroll.cycles);
  const { data: settings } = useFetch<PayrollSettings>(API.payroll.settings);
  const { data: salaryPage } =
    useFetch<PagedResponse<EmployeeSalaryConfig>>(API.payroll.employeeSalary);

  const [cancelTarget, setCancelTarget] = useState<PayrollCycle | null>(null);

  const cycles   = cyclesPage?.results ?? [];
  const empCount = salaryPage?.count ?? 0;

  const pending = cycles.filter(c => !["paid", "closed", "cancelled"].includes(c.status));
  const paid    = cycles.filter(c =>  ["paid", "closed"].includes(c.status));

  const now      = new Date();
  const year     = now.getFullYear();
  const month    = now.getMonth();
  const today    = now.getDate();
  const payDay   = settings?.pay_day ?? 30;
  const monthName = now.toLocaleString("en-IN", { month: "long" });

  const { firstDay, days } = getCalendarDates(year, month);
  const calDates = Array.from({ length: days }, (_, i) => i + 1);

  const STATS = [
    {
      label: "Employees w/ Salary",
      value: empCount > 0 ? String(empCount) : "—",
      sub: "CTC configured",
      icon: "ti-users",
      cls: "si-primary",
    },
    {
      label: "Pending Cycles",
      value: String(pending.length),
      sub: pending.length > 0 ? `${pending.length} need action` : "All up to date",
      icon: "ti-clock",
      cls: pending.length > 0 ? "si-warn" : "si-success",
    },
    {
      label: "Paid This Year",
      value: String(paid.length),
      sub: "Completed payroll runs",
      icon: "ti-circle-check",
      cls: "si-success",
    },
    {
      label: "Next Pay Day",
      value: payDay ? `${payDay} ${monthName}` : "—",
      sub: settings ? `Cycle ${settings.cycle_start_day}–${settings.cycle_end_day}` : "Not configured",
      icon: "ti-calendar-event",
      cls: "si-info",
    },
    {
      label: "Total Payroll Runs",
      value: String(cycles.length),
      sub: "All time",
      icon: "ti-history",
      cls: "si-primary",
    },
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
          <div className="card-header">
            <div className="card-title"><i className="ti ti-calendar-event" /> Payroll Calendar</div>
            <span className="badge badge-primary">{monthName} {year}</span>
          </div>
          <div className="card-body" style={{ padding: 16 }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 2, marginBottom: 8 }}>
              {DAYS_LABEL.map((d, i) => (
                <div key={i} style={{ textAlign: "center", fontSize: 10, fontWeight: 600, color: "var(--on-variant)", padding: "4px 0" }}>{d}</div>
              ))}
              {Array.from({ length: firstDay }).map((_, i) => <div key={`e${i}`} />)}
              {calDates.map(d => {
                const isPayDay = d === payDay;
                const isToday  = d === today;
                return (
                  <div
                    key={d}
                    style={{
                      textAlign: "center", fontSize: 12, padding: "5px 2px",
                      borderRadius: 6, fontWeight: isToday ? 700 : 400,
                      background: isPayDay ? "var(--primary)" : "transparent",
                      color: isPayDay ? "#fff" : "var(--on-bg)",
                      border: isToday && !isPayDay ? "1.5px solid var(--primary)" : "none",
                    }}
                  >
                    {d}
                  </div>
                );
              })}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 12, borderTop: "1px solid var(--outline-v)", paddingTop: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
                <div style={{ width: 12, height: 12, borderRadius: 3, background: "var(--primary)" }} />
                <span>Salary Date — {payDay} {monthName}</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
                <div style={{ width: 12, height: 12, borderRadius: 3, border: "2px solid var(--primary)" }} />
                <span>Today — {today} {monthName}</span>
              </div>
            </div>
            <button className="btn btn-filled btn-sm" style={{ width: "100%", marginTop: 14, justifyContent: "center" }} onClick={onRunPayroll}>
              <i className="ti ti-player-play" /> Run {monthName} Payroll
            </button>
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
              <button className="btn btn-filled btn-sm" onClick={onRunPayroll}>
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
                  {cycles.map(c => (
                    <tr key={c.id} style={{ cursor: canResume ? "pointer" : "default" }} onClick={canResume ? () => onResumeCycle(c.id, c.status) : undefined}>
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
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Quick actions if there are pending cycles */}
      {pending.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title"><i className="ti ti-alert-circle" style={{ color: "var(--warn)" }} /> Action Required — {pending.length} Pending Cycle{pending.length !== 1 ? "s" : ""}</div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Period</th>
                  <th>Pay Date</th>
                  <th>Status</th>
                  <th>L1 Approver</th>
                  <th>Payslips</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {pending.map(c => (
                  <tr key={c.id} style={{ cursor: canResume ? "pointer" : "default" }} onClick={canResume ? () => onResumeCycle(c.id, c.status) : undefined}>
                    <td style={{ fontWeight: 600 }}>
                      {new Date(c.cycle_start).toLocaleString("en-IN", { month: "long", year: "numeric" })}
                    </td>
                    <td>{c.pay_date}</td>
                    <td>
                      <span className={STATUS_BADGE[c.status] ?? "badge badge-neutral"}>
                        {STATUS_LABEL[c.status] ?? c.status}
                      </span>
                    </td>
                    <td style={{ fontSize: 13, color: "var(--on-variant)" }}>{c.l1_approver_name ?? "—"}</td>
                    <td>{c.payslip_count}</td>
                    <td onClick={e => e.stopPropagation()}>
                      {!UNCANCELLABLE.includes(c.status) && (
                        <button
                          className="btn btn-ghost btn-sm"
                          style={{ color: "var(--error)", fontSize: 12 }}
                          onClick={() => setCancelTarget(c)}
                          title="Cancel this cycle"
                        >
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

      {/* Cancelled cycles (collapsed, audit trail) */}
      {cycles.some(c => c.status === "cancelled") && (
        <details className="card" style={{ padding: 0 }}>
          <summary style={{ padding: "12px 16px", cursor: "pointer", fontWeight: 600, fontSize: 13, listStyle: "none", display: "flex", alignItems: "center", gap: 8 }}>
            <i className="ti ti-ban" style={{ color: "var(--error)" }} />
            Cancelled Cycles ({cycles.filter(c => c.status === "cancelled").length})
          </summary>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Period</th>
                  <th>Cancelled By</th>
                  <th>Cancelled At</th>
                  <th>Reason</th>
                </tr>
              </thead>
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
