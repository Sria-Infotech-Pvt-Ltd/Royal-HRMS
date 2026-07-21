"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import EmployeeAttendanceRow, { type EmployeeRow } from "./EmployeeAttendanceRow";

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
  };
  employees: EmployeeRow[];
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmtDate = (d: string) =>
  new Date(d).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });

const fmtMonth = (d: string) =>
  new Date(d).toLocaleDateString("en-IN", { month: "long", year: "numeric" });

// ── Main component ─────────────────────────────────────────────────────────────

export default function AttendanceApprovalTab() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [comment,    setComment]    = useState("");
  const [approving,  setApproving]  = useState(false);
  const [apiErr,     setApiErr]     = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const { data: cycles, loading: cyclesLoading, error: cyclesError, refetch: refetchCycles } =
    useFetch<PendingCycle[]>(API.payroll.pendingApprovalCycles);

  const { data: summary, loading: summaryLoading, refetch: refetchSummary } =
    useFetch<CycleSummary>(selectedId ? API.payroll.attendanceSummary(selectedId) : null);

  const selected = cycles?.find(c => c.id === selectedId) ?? null;

  // Determine which approval level the current user should act on
  const l1Done = !!summary?.cycle.l1_approver;
  const l2Done = !!summary?.cycle.l2_approver;
  const needsL1 = !l1Done;
  const needsL2 = l1Done && !l2Done;
  const approvalLevel = needsL1 ? 1 : needsL2 ? 2 : null;

  async function approve() {
    if (!selectedId || !approvalLevel) return;
    setApproving(true); setApiErr(null);
    try {
      await clientApi.post(API.payroll.approveAttendance(selectedId), {
        level: `L${approvalLevel}`,
        comment,
      });
      setSuccessMsg(`L${approvalLevel} attendance approval recorded.`);
      setComment("");
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
                background: selectedId === c.id ? "rgba(30,78,140,0.07)" : "var(--bg)",
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
          <div style={{ padding: "14px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
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

            {/* L1 / L2 status pills */}
            <div style={{ display: "flex", gap: 8 }}>
              <span style={{
                padding: "4px 12px", borderRadius: 20, fontSize: 11, fontWeight: 600,
                background: summary?.cycle.l1_approver ? "rgba(34,197,94,0.12)" : "rgba(234,179,8,0.12)",
                color:      summary?.cycle.l1_approver ? "#15803d"                : "#92400e",
              }}>
                L1 {summary?.cycle.l1_approver ? `✓ ${summary.cycle.l1_approver}` : "Pending"}
              </span>
              <span style={{
                padding: "4px 12px", borderRadius: 20, fontSize: 11, fontWeight: 600,
                background: summary?.cycle.l2_approver ? "rgba(34,197,94,0.12)" : "rgba(100,116,139,0.10)",
                color:      summary?.cycle.l2_approver ? "#15803d"                : "var(--on-variant)",
              }}>
                L2 {summary?.cycle.l2_approver ? `✓ ${summary.cycle.l2_approver}` : "Waiting"}
              </span>
            </div>
          </div>

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
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Approval footer — only shown if action is still needed */}
          {approvalLevel && !summaryLoading && (
            <div style={{ padding: "16px 20px", borderTop: "1px solid var(--border)", background: "var(--bg)", display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>
                <i className="ti ti-user-check" style={{ marginRight: 6, color: "var(--primary)" }} />
                {approvalLevel === 1 ? "Manager (L1) — Review and approve attendance records" : "HR (L2) — Final sign-off on attendance"}
              </div>
              <textarea
                className="field-input"
                rows={2}
                placeholder="Add approval note (optional)…"
                value={comment}
                onChange={e => setComment(e.target.value)}
                style={{ resize: "vertical" }}
              />
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <button
                  className="btn btn-filled"
                  onClick={approve}
                  disabled={approving || summaryLoading}
                >
                  {approving
                    ? <><i className="ti ti-loader-2 spin" /> Approving…</>
                    : <><i className="ti ti-check" /> Approve L{approvalLevel} Attendance</>
                  }
                </button>
              </div>
            </div>
          )}

          {!approvalLevel && !summaryLoading && summary && (
            <div style={{ padding: "14px 20px", borderTop: "1px solid var(--border)", background: "rgba(34,197,94,0.06)", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "#15803d", fontWeight: 600 }}>
              <i className="ti ti-circle-check" style={{ fontSize: 16 }} />
              Attendance fully approved — L1 and L2 sign-off complete.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

