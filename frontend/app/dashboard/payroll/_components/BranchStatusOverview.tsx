"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";

interface BranchPayrollStatus {
  branch_id:   string;
  branch_name: string;
  branch_code: string;
  status:      string | null;
  cycle_id:    string | null;
  cycle_start: string | null;
  cycle_end:   string | null;
  paid_at:     string | null;
}

interface Props {
  onRunBranch:    (branchId: string, branchName: string) => void;
  onResumeBranch: (cycleId: string, status: string, cycleStart?: string) => void;
}

const IN_PROGRESS_STATUSES = new Set([
  "draft",
  "attendance_pending",
  "attendance_approved",
  "processing",
  "payslips_generated",
  "query_window_open",
]);

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

function fmt(dateStr: string | null) {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export default function BranchStatusOverview({ onRunBranch, onResumeBranch }: Props) {
  const { data, loading, error, refetch } =
    useFetch<BranchPayrollStatus[]>(API.payroll.branchStatus);

  if (loading) {
    return (
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <div className="card-title"><i className="ti ti-building-bank" /> Branch Payroll Status</div>
        </div>
        <div style={{ padding: 32, textAlign: "center", color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 animate-spin" style={{ fontSize: 24 }} />
          <div style={{ marginTop: 8, fontSize: 13 }}>Loading branch status…</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <div className="card-title"><i className="ti ti-building-bank" /> Branch Payroll Status</div>
        </div>
        <div className="alert alert-error" style={{ margin: 20 }}>
          <i className="ti ti-alert-circle" />
          <span>Failed to load branch status. <button className="btn btn-ghost btn-sm" onClick={refetch}>Retry</button></span>
        </div>
      </div>
    );
  }

  const branches = data ?? [];
  const paidCount      = branches.filter(b => b.status === "paid" || b.status === "closed").length;
  const inProgressCount = branches.filter(b => b.status && IN_PROGRESS_STATUSES.has(b.status)).length;
  const pendingCount   = branches.filter(b => !b.status).length;

  return (
    <div className="card" style={{ marginBottom: 24 }}>
      <div className="card-header">
        <div className="card-title">
          <i className="ti ti-building-bank" /> Branch Payroll Status
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <span style={{ fontSize: 12, color: "var(--on-variant)" }}>
            {branches.length} branch{branches.length !== 1 ? "es" : ""}
          </span>
          <button className="btn btn-ghost btn-sm" onClick={refetch}>
            <i className="ti ti-refresh" /> Refresh
          </button>
        </div>
      </div>

      {/* Summary strip */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(3, 1fr)",
        gap: 1, background: "var(--outline-v)",
        borderBottom: "1px solid var(--outline-v)",
      }}>
        {[
          { label: "Paid / Closed",   count: paidCount,       color: "var(--success)", icon: "ti-circle-check" },
          { label: "In Progress",      count: inProgressCount, color: "var(--primary)", icon: "ti-loader-2"     },
          { label: "Not Started",      count: pendingCount,    color: "var(--on-variant)", icon: "ti-clock"     },
        ].map(item => (
          <div key={item.label} style={{
            padding: "14px 20px", background: "var(--bg)",
            display: "flex", alignItems: "center", gap: 12,
          }}>
            <i className={`ti ${item.icon}`} style={{ color: item.color, fontSize: 20 }} />
            <div>
              <div style={{ fontSize: 22, fontWeight: 700, lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>
                {item.count}
              </div>
              <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 2 }}>{item.label}</div>
            </div>
          </div>
        ))}
      </div>

      {branches.length === 0 ? (
        <div style={{ padding: 32, textAlign: "center", color: "var(--on-variant)", fontSize: 14 }}>
          No active branches found. Add branches in Settings → Branch Management.
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "var(--bg-low)" }}>
                {["Branch", "Code", "Current Cycle", "Period", "Status", "Action"].map(h => (
                  <th key={h} style={{
                    padding: "10px 16px", textAlign: "left",
                    fontSize: 11, fontWeight: 700, color: "var(--on-variant)",
                    textTransform: "uppercase", letterSpacing: "0.04em",
                    borderBottom: "1px solid var(--outline-v)",
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {branches.map((branch, idx) => {
                const isInProgress = branch.status && IN_PROGRESS_STATUSES.has(branch.status);
                const isPaid = branch.status === "paid" || branch.status === "closed";

                return (
                  <tr key={branch.branch_id} style={{
                    background: idx % 2 === 0 ? "var(--bg)" : "var(--bg-low)",
                    borderBottom: "1px solid var(--outline-v)",
                  }}>
                    <td style={{ padding: "12px 16px", fontWeight: 600, fontSize: 14 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <i className="ti ti-building" style={{ color: "var(--primary)", fontSize: 14 }} />
                        {branch.branch_name}
                      </div>
                    </td>
                    <td style={{ padding: "12px 16px", fontSize: 12, color: "var(--on-variant)", fontVariantNumeric: "tabular-nums" }}>
                      {branch.branch_code || "—"}
                    </td>
                    <td style={{ padding: "12px 16px", fontSize: 13 }}>
                      {branch.cycle_start ? (
                        <span style={{ fontVariantNumeric: "tabular-nums" }}>
                          Cycle #{branch.cycle_id?.slice(-6)}
                        </span>
                      ) : (
                        <span style={{ color: "var(--on-variant)", fontSize: 12 }}>No active cycle</span>
                      )}
                    </td>
                    <td style={{ padding: "12px 16px", fontSize: 12, color: "var(--on-variant)", fontVariantNumeric: "tabular-nums" }}>
                      {branch.cycle_start
                        ? `${fmt(branch.cycle_start)} – ${fmt(branch.cycle_end)}`
                        : "—"}
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      {branch.status ? (
                        <span className={STATUS_BADGE[branch.status] ?? "badge badge-neutral"}>
                          {STATUS_LABEL[branch.status] ?? branch.status}
                        </span>
                      ) : (
                        <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Not started</span>
                      )}
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      {isPaid ? (
                        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--success)" }}>
                          <i className="ti ti-circle-check" />
                          {branch.paid_at ? `Paid ${fmt(branch.paid_at)}` : "Paid"}
                        </div>
                      ) : isInProgress && branch.cycle_id && branch.status ? (
                        <button
                          className="btn btn-outline btn-sm"
                          onClick={() => onResumeBranch(branch.cycle_id!, branch.status!, branch.cycle_start ?? undefined)}
                        >
                          <i className="ti ti-player-play" /> Resume
                        </button>
                      ) : (
                        <button
                          className="btn btn-filled btn-sm"
                          onClick={() => onRunBranch(branch.branch_id, branch.branch_name)}
                        >
                          <i className="ti ti-player-play" /> Run Payroll
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
