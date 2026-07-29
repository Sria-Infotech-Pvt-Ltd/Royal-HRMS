"use client";

import { useLeaveBalances } from "@/hooks/useEmployeeDashboard";
import { useFiscalYearConfig } from "@/lib/fiscalYear";
import AssessmentLockedNotice from "./AssessmentLockedNotice";

const LEAVE_TYPE_LABEL: Record<string, string> = {
  casual:    "Casual Leave",
  sick:      "Sick Leave",
  earned:    "Earned Leave",
  maternity: "Maternity Leave",
  paternity: "Paternity Leave",
  lwp:       "Leave Without Pay",
};

const LEAVE_TYPE_COLOR: Record<string, string> = {
  casual:    "var(--info)",
  sick:      "var(--warn)",
  earned:    "var(--success)",
  maternity: "var(--secondary)",
  paternity: "var(--primary)",
  lwp:       "var(--outline)",
};

export default function EmpLeaveBalances() {
  const { currentYear: year } = useFiscalYearConfig();
  const { data, loading, status } = useLeaveBalances(year);

  const balances = data?.balances ?? [];

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-beach" /> Leave Balances — {year}</div>
        <a href="/dashboard/leave" className="btn btn-ghost btn-sm">Apply Leave</a>
      </div>

      {loading ? (
        <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
        </div>
      ) : status === 403 ? (
        <AssessmentLockedNotice />
      ) : balances.length === 0 ? (
        <div style={{ padding: "24px 20px", textAlign: "center", fontSize: 13, color: "var(--on-variant)" }}>
          No leave balances found. Contact HR to credit your leave.
        </div>
      ) : (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))" }}>
            {balances.map(b => {
              const pct   = b.total_days > 0 ? Math.min(100, (b.remaining / b.total_days) * 100) : 0;
              const color = LEAVE_TYPE_COLOR[b.leave_type] ?? "var(--primary)";
              const label = LEAVE_TYPE_LABEL[b.leave_type] ?? b.leave_type;
              return (
                <div key={b.leave_type} style={{ padding: "12px 16px", borderRight: "1px solid var(--border)", borderBottom: "1px solid var(--border)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                    <span style={{ width: 8, height: 8, borderRadius: 2, background: color, flexShrink: 0 }} />
                    <span style={{ fontSize: 12, fontWeight: 600, color: "var(--on-bg)" }}>{label}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontSize: 20, fontWeight: 800, color: "var(--on-bg)", lineHeight: 1 }}>{b.remaining}</span>
                    <span style={{ fontSize: 11, color: "var(--on-variant)", alignSelf: "flex-end" }}>of {b.total_days} days</span>
                  </div>
                  <div style={{ height: 5, borderRadius: 3, background: "var(--bg-high)", overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 3, transition: "width 0.4s ease" }} />
                  </div>
                  {b.used_days > 0 && (
                    <div style={{ fontSize: 10, color: "var(--on-variant)", marginTop: 4 }}>{b.used_days} used{b.carried_forward > 0 ? ` · ${b.carried_forward} carried forward` : ""}</div>
                  )}
                </div>
              );
            })}
          </div>
          {(data?.lop_days ?? 0) > 0 && (
            <div style={{ padding: "8px 16px", borderTop: "1px solid var(--border)", fontSize: 12, color: "var(--error)", display: "flex", alignItems: "center", gap: 6 }}>
              <i className="ti ti-alert-circle" style={{ fontSize: 13 }} />
              {data?.lop_days} LOP day{(data?.lop_days ?? 0) !== 1 ? "s" : ""} this year
            </div>
          )}
        </>
      )}
    </div>
  );
}
