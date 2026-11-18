"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { ManagerApproval } from "@/types/payroll";
import EmployeeAttendanceRow, { type EmployeeRow } from "./EmployeeAttendanceRow";
import { formatDate } from "@/lib/formatDate";
import AttendanceCycleSteps from "./AttendanceCycleSteps";
import AttendanceTotals from "./AttendanceTotals";
import { AttendanceApprovalStyles } from "./attendanceApprovalStyles";

// ── Types ─────────────────────────────────────────────────────────────────────

interface PendingCycle {
  id: string;
  cycle_start: string;
  cycle_end: string;
  pay_date: string;
  status: string;
  l1_approver_name: string | null;
  l2_approver_name: string | null;
  attendance_l1_approved_at: string | null;
  attendance_l2_approved_at: string | null;
  payslip_count: number;
}

interface CycleSummary {
  cycle: {
    id: string;
    cycle_start: string;
    cycle_end: string;
    pay_date: string;
    status: string;
    l1_approver: string | null;
    l2_approver: string | null;
    l1_approved_at: string | null;
    l2_approved_at: string | null;
    hr_self_approved_at: string | null;
    manager_approvals: ManagerApproval[];
    mgr_approved_count: number;
    mgr_total_count: number;
    mgr_all_approved: boolean;
    current_user_pending: boolean;
  };
  employees: EmployeeRow[];
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmtDate = (d: string) => formatDate(d);

const fmtMonth = (d: string) =>
  new Date(d).toLocaleDateString("en-IN", { month: "long", year: "numeric" });

/** Employees who deserve a second look before sign-off: any absence or loss-of-pay day. */
const needsAttention = (employee: EmployeeRow) => employee.absent_days > 0 || employee.lop_days > 0;

// ── Main component ─────────────────────────────────────────────────────────────

export default function AttendanceApprovalTab() {
  const [selectedId,  setSelectedId]  = useState<string | null>(null);
  const [comment,     setComment]     = useState("");
  const [selfApprove, setSelfApprove] = useState(false);
  const [approving,   setApproving]   = useState(false);
  const [apiErr,      setApiErr]      = useState<string | null>(null);
  const [successMsg,  setSuccessMsg]  = useState<string | null>(null);
  const [query,        setQuery]        = useState("");
  const [isAttentionOnly, setIsAttentionOnly] = useState(false);

  const { data: cycles, loading: cyclesLoading, error: cyclesError, refetch: refetchCycles } =
    useFetch<PendingCycle[]>(API.payroll.pendingApprovalCycles);

  const { data: summary, loading: summaryLoading, refetch: refetchSummary } =
    useFetch<CycleSummary>(selectedId ? API.payroll.attendanceSummary(selectedId) : null);

  const selected = cycles?.find(c => c.id === selectedId) ?? null;

  const allEmployees = summary?.employees ?? [];
  const attentionCount = allEmployees.filter(needsAttention).length;
  const needle = query.trim().toLowerCase();
  const visibleEmployees = allEmployees.filter(employee =>
    (!isAttentionOnly || needsAttention(employee)) &&
    (!needle || `${employee.full_name} ${employee.employee_id} ${employee.department}`.toLowerCase().includes(needle)));

  const l1Done            = !!summary?.cycle.l1_approver;
  const l2Done            = !!summary?.cycle.l2_approver;
  const currentUserPending = summary?.cycle.current_user_pending ?? false;
  const mgrApprovals      = summary?.cycle.manager_approvals ?? [];
  const mgrApprovedCount  = summary?.cycle.mgr_approved_count ?? 0;
  const mgrTotalCount     = summary?.cycle.mgr_total_count ?? 0;

  // Determine what action the current user can take
  // When no manager has team-lead rights configured at all for this cycle
  // (mgrTotalCount === 0), nobody will ever have a ManagerAttendanceApproval
  // row, so current_user_pending can never be true -- that's exactly the
  // "no managers configured" bypass case, where whoever can see this cycle
  // at all (HR/Admin, gated server-side) is also allowed to approve L1
  // directly (backend's AttendanceApprovalView has the matching fallback).
  const noManagersConfigured = mgrTotalCount === 0;
  const canDoL1 = (currentUserPending || noManagersConfigured) && !l1Done;
  const canDoL2 = l1Done && !l2Done;
  const approvalLevel: 1 | 2 | null = canDoL1 ? 1 : canDoL2 ? 2 : null;

  async function approve() {
    if (!selectedId || !approvalLevel) return;
    setApproving(true); setApiErr(null);
    try {
      await clientApi.post(API.payroll.approveAttendance(selectedId), {
        level: `L${approvalLevel}`,
        comment,
        self_approve: selfApprove,
      });
      setSuccessMsg(`L${approvalLevel} attendance approval recorded.`);
      setComment("");
      setSelfApprove(false);
      refetchSummary();
      refetchCycles();
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Approval failed. Please try again.";
      setApiErr(msg);
    } finally {
      setApproving(false);
    }
  }

  if (cyclesLoading) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "60px 20px", justifyContent: "center", fontSize: 13, color: "var(--on-variant)" }}>
        <i className="ti ti-loader-2 animate-spin" style={{ fontSize: 20, color: "var(--primary)" }} />
        Loading pending approval cycles…
      </div>
    );
  }

  if (cyclesError) {
    return <div className="alert alert-error"><i className="ti ti-alert-circle" /> {cyclesError}</div>;
  }

  if (!cycles || cycles.length === 0) {
    return (
      <div style={{ padding: "60px 20px", textAlign: "center", color: "var(--on-variant)" }}>
        <i className="ti ti-checks" style={{ fontSize: 40, display: "block", marginBottom: 12, opacity: 0.3 }} />
        <div style={{ fontSize: 14 }}>No payroll cycles pending your attendance approval.</div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {successMsg && <div className="alert alert-success"><i className="ti ti-circle-check" /> {successMsg}</div>}
      {apiErr     && <div className="alert alert-error"><i className="ti ti-alert-circle" /> {apiErr}</div>}

      <AttendanceApprovalStyles />

      {/* Cycle selector */}
      <div>
        <div style={{ fontSize: 12, fontWeight: 700, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: ".05em", marginBottom: 8 }}>
          Select payroll period
        </div>
        <div className="aa-cycles">
          {cycles.map(c => (
            <button
              key={c.id}
              type="button"
              className={`aa-cycle${selectedId === c.id ? " is-on" : ""}`}
              aria-pressed={selectedId === c.id}
              onClick={() => { setSelectedId(c.id); setApiErr(null); setQuery(""); setIsAttentionOnly(false); }}
            >
              <b>{fmtMonth(c.cycle_start)}</b>
              <small>{fmtDate(c.cycle_start)} → {fmtDate(c.cycle_end)}</small>
              <small>Pay date: {fmtDate(c.pay_date)}</small>
              <span className="aa-cycle-chips">
                <span className={`aa-chip ${c.attendance_l1_approved_at ? "is-done" : "is-open"}`}>L1 {c.attendance_l1_approved_at ? "done" : "open"}</span>
                <span className={`aa-chip ${c.attendance_l2_approved_at ? "is-done" : "is-open"}`}>L2 {c.attendance_l2_approved_at ? "done" : "open"}</span>
                <span className="aa-chip">{c.payslip_count} payslip{c.payslip_count === 1 ? "" : "s"}</span>
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Summary panel */}
      {selectedId && (
        <div className="card">

          {/* Cycle header */}
          <div style={{ padding: "14px 20px", borderBottom: "1px solid var(--outline-v)", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>
                Attendance — {selected ? fmtMonth(selected.cycle_start) : ""}
              </div>
              {selected && (
                <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
                  {fmtDate(selected.cycle_start)} → {fmtDate(selected.cycle_end)}  ·  Pay date {fmtDate(selected.pay_date)}
                </div>
              )}
            </div>
          </div>

          {!summaryLoading && summary && (
            <>
              <AttendanceCycleSteps
                managers={mgrApprovals}
                managersApproved={mgrApprovedCount}
                managersTotal={mgrTotalCount}
                isL1Done={l1Done}
                isL2Done={l2Done}
                l2Name={summary.cycle.l2_approver}
                isHrSelfApproved={Boolean(summary.cycle.hr_self_approved_at)}
              />
              {allEmployees.length > 0 && <AttendanceTotals employees={allEmployees} />}
            </>
          )}

          {/* Attendance table */}
          {summaryLoading ? (
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "40px 20px", justifyContent: "center", fontSize: 13, color: "var(--on-variant)" }}>
              <i className="ti ti-loader-2 animate-spin" style={{ fontSize: 18, color: "var(--primary)" }} /> Loading attendance data…
            </div>
          ) : !summary || summary.employees.length === 0 ? (
            <div style={{ padding: "40px 20px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
              No attendance records found for this period.
            </div>
          ) : (
            <>
            <div className="aa-find">
              <div className="aa-find-box">
                <i className="ti ti-search" />
                <input type="search" placeholder="Search name, ID or department…" aria-label="Search employees" value={query} onChange={e => setQuery(e.target.value)} />
              </div>
              <button type="button" className={`aa-filter${isAttentionOnly ? " is-on" : ""}`} aria-pressed={isAttentionOnly} onClick={() => setIsAttentionOnly(v => !v)}>
                <i className="ti ti-alert-triangle" /> Needs a look ({attentionCount})
              </button>
              <span className="aa-find-count">Showing {visibleEmployees.length} of {allEmployees.length}</span>
            </div>
            {visibleEmployees.length === 0 ? (
              <div className="aa-empty"><i className="ti ti-mood-check" />Nobody matches. Clear the search or the filter.</div>
            ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid var(--outline-v)" }}>
                    {["Employee", "Department", "Present", "Late", "Half Day", "On Leave", "Absent", "LOP Days", "Hrs Worked"].map(h => (
                      <th key={h} style={{ padding: "10px 12px", textAlign: h === "Employee" || h === "Department" ? "left" : "center", color: "var(--on-variant)", fontWeight: 600, whiteSpace: "nowrap", fontSize: 12 }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {visibleEmployees.map(emp => (
                    <EmployeeAttendanceRow
                      key={emp.employee_id}
                      emp={emp}
                      cycleId={selectedId}
                      cycleStart={summary.cycle.cycle_start}
                    />
                  ))}
                </tbody>
              </table>
            </div>
            )}
            </>
          )}

          {/* Approval footer */}
          {approvalLevel && !summaryLoading && (
            <div style={{ padding: "16px 20px", borderTop: "1px solid var(--outline-v)", background: "var(--bg)", display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>
                <i className="ti ti-user-check" style={{ marginRight: 6, color: "var(--primary)" }} />
                {approvalLevel === 1
                  ? noManagersConfigured
                    ? "No managers have team-lead rights configured for this cycle — HR/Admin can approve L1 directly"
                    : "Your sign-off is required — review your team's attendance and approve"
                  : "HR (L2) — Final sign-off on attendance"}
              </div>
              <textarea
                className="field-input"
                rows={2}
                placeholder="Add approval note (optional)…"
                value={comment}
                onChange={e => setComment(e.target.value)}
                style={{ resize: "vertical" }}
              />
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--on-variant)", cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={selfApprove}
                  onChange={e => setSelfApprove(e.target.checked)}
                />
                I also confirm my own attendance for this period is accurate (self-attested)
              </label>
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <button
                  className="btn btn-filled"
                  onClick={approve}
                  disabled={approving || summaryLoading}
                >
                  {approving
                    ? <><i className="ti ti-loader-2 animate-spin" /> Approving…</>
                    : <><i className="ti ti-check" /> Approve L{approvalLevel} Attendance</>
                  }
                </button>
              </div>
            </div>
          )}

          {/* Waiting for other managers */}
          {!approvalLevel && !currentUserPending && !l1Done && !summaryLoading && summary && (
            <div style={{ padding: "14px 20px", borderTop: "1px solid var(--outline-v)", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
              <i className="ti ti-clock" />
              You have approved. Waiting for {mgrTotalCount - mgrApprovedCount} other manager(s) to sign off.
            </div>
          )}

          {/* Fully approved */}
          {!approvalLevel && (l1Done && l2Done) && !summaryLoading && summary && (
            <div style={{ padding: "14px 20px", borderTop: "1px solid var(--outline-v)", background: "rgba(34,197,94,0.06)", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "#15803d", fontWeight: 600 }}>
              <i className="ti ti-circle-check" style={{ fontSize: 16 }} />
              Attendance fully approved — L1 and L2 sign-off complete.
            </div>
          )}

        </div>
      )}
    </div>
  );
}
