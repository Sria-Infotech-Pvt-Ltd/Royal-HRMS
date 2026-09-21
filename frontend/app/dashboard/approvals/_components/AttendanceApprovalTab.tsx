"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { ManagerApproval } from "@/types/payroll";
import EmployeeAttendanceRow, { type EmployeeRow } from "./EmployeeAttendanceRow";
import { formatDate } from "@/lib/formatDate";

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

const fmtDateTime = (d: string) =>
  new Date(d).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

// ── Main component ─────────────────────────────────────────────────────────────

export default function AttendanceApprovalTab() {
  const [selectedId,  setSelectedId]  = useState<string | null>(null);
  const [comment,     setComment]     = useState("");
  const [selfApprove, setSelfApprove] = useState(false);
  const [approving,   setApproving]   = useState(false);
  const [apiErr,      setApiErr]      = useState<string | null>(null);
  const [successMsg,  setSuccessMsg]  = useState<string | null>(null);

  const { data: cycles, loading: cyclesLoading, error: cyclesError, refetch: refetchCycles } =
    useFetch<PendingCycle[]>(API.payroll.pendingApprovalCycles);

  const { data: summary, loading: summaryLoading, refetch: refetchSummary } =
    useFetch<CycleSummary>(selectedId ? API.payroll.attendanceSummary(selectedId) : null);

  const selected = cycles?.find(c => c.id === selectedId) ?? null;

  const l1Done            = !!summary?.cycle.l1_approver;
  const l2Done            = !!summary?.cycle.l2_approver;
  const currentUserPending = summary?.cycle.current_user_pending ?? false;
  const mgrAllApproved    = summary?.cycle.mgr_all_approved ?? false;
  const mgrApprovals      = summary?.cycle.manager_approvals ?? [];
  const mgrApprovedCount  = summary?.cycle.mgr_approved_count ?? 0;
  const mgrTotalCount     = summary?.cycle.mgr_total_count ?? 0;

  // Determine what action the current user can take
  const canDoL1 = currentUserPending && !l1Done;
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

      {/* Cycle selector */}
      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: ".05em", marginBottom: 8 }}>
          Select Payroll Period
        </div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {cycles.map(c => (
            <button
              key={c.id}
              onClick={() => { setSelectedId(c.id); setApiErr(null); }}
              style={{
                padding: "10px 18px", borderRadius: 10, border: "1.5px solid",
                borderColor: selectedId === c.id ? "var(--primary)" : "var(--outline-v)",
                background: selectedId === c.id ? "rgba(124,58,237,0.07)" : "var(--bg)",
                color: selectedId === c.id ? "var(--primary)" : "var(--on-bg)",
                cursor: "pointer", fontSize: 13, fontWeight: selectedId === c.id ? 700 : 500,
                transition: "all 0.12s",
              }}
            >
              <div>{fmtMonth(c.cycle_start)}</div>
              <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 2 }}>
                Pay date: {fmtDate(c.pay_date)}
              </div>
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

            {/* Approval status pills */}
            {!summaryLoading && summary && (
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {/* L1: per-manager count */}
                <span style={{
                  padding: "4px 12px", borderRadius: 20, fontSize: 11, fontWeight: 600,
                  background: l1Done ? "rgba(34,197,94,0.12)" : mgrApprovedCount > 0 ? "rgba(234,179,8,0.12)" : "rgba(100,116,139,0.10)",
                  color: l1Done ? "#15803d" : mgrApprovedCount > 0 ? "#92400e" : "var(--on-variant)",
                }}>
                  {mgrTotalCount > 0
                    ? l1Done
                      ? `L1 ✓ All managers (${mgrTotalCount})`
                      : `L1 ${mgrApprovedCount}/${mgrTotalCount} managers`
                    : l1Done
                      ? "L1 ✓ Approved"
                      : "L1 Pending"
                  }
                </span>
                {/* L2 */}
                <span style={{
                  padding: "4px 12px", borderRadius: 20, fontSize: 11, fontWeight: 600,
                  background: l2Done ? "rgba(34,197,94,0.12)" : "rgba(100,116,139,0.10)",
                  color: l2Done ? "#15803d" : "var(--on-variant)",
                }}>
                  {l2Done ? `L2 ✓ ${summary.cycle.l2_approver}` : "L2 Waiting"}
                </span>
                {summary.cycle.hr_self_approved_at && (
                  <span style={{
                    padding: "4px 12px", borderRadius: 20, fontSize: 11, fontWeight: 700,
                    background: "rgba(217,119,6,0.12)", color: "#b45309",
                  }}>
                    HR Self-Approved
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Per-manager approval breakdown — shown when there are manager rows */}
          {!summaryLoading && mgrTotalCount > 0 && (
            <div style={{ padding: "12px 20px", borderBottom: "1px solid var(--outline-v)", display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
                Manager Sign-offs ({mgrApprovedCount}/{mgrTotalCount} approved)
              </div>
              {/* Progress bar */}
              <div style={{ height: 4, borderRadius: 99, background: "var(--bg-high)", overflow: "hidden", marginBottom: 4 }}>
                <div style={{
                  height: "100%", borderRadius: 99,
                  width: mgrTotalCount > 0 ? `${(mgrApprovedCount / mgrTotalCount) * 100}%` : "0%",
                  background: mgrAllApproved ? "var(--success)" : "var(--primary)",
                  transition: "width 0.4s ease",
                }} />
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {mgrApprovals.map(row => (
                  <div
                    key={row.id}
                    style={{
                      display: "flex", alignItems: "center", gap: 7,
                      padding: "5px 12px", borderRadius: 20,
                      border: `1.5px solid ${row.approved_at ? "var(--success)" : "var(--outline-v)"}`,
                      background: row.approved_at ? "rgba(34,197,94,0.07)" : "var(--bg-low)",
                      fontSize: 12,
                    }}
                  >
                    <i
                      className={`ti ${row.approved_at ? "ti-circle-check" : "ti-clock"}`}
                      style={{ color: row.approved_at ? "var(--success)" : "var(--on-variant)", fontSize: 13 }}
                    />
                    <span style={{ fontWeight: 600 }}>{row.manager_name}</span>
                    {row.approved_at && (
                      <span style={{ color: "var(--on-variant)", fontSize: 11 }}>
                        {fmtDateTime(row.approved_at)}
                      </span>
                    )}
                    {row.self_approved_at && (
                      <span style={{
                        padding: "2px 8px", borderRadius: 20, fontSize: 10, fontWeight: 700,
                        background: "rgba(217,119,6,0.12)", color: "#b45309",
                      }}>
                        Self-Approved
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
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
                  {summary.employees.map(emp => (
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

          {/* Approval footer */}
          {approvalLevel && !summaryLoading && (
            <div style={{ padding: "16px 20px", borderTop: "1px solid var(--outline-v)", background: "var(--bg)", display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>
                <i className="ti ti-user-check" style={{ marginRight: 6, color: "var(--primary)" }} />
                {approvalLevel === 1
                  ? "Your sign-off is required — review your team's attendance and approve"
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
