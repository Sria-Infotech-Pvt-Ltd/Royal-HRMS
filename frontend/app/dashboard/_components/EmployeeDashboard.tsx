"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { SessionPayload } from "@/lib/session";
import ClockInButton from "@/components/ClockInButton";

interface Props { session: SessionPayload }

interface LeaveBalance {
  id: string;
  leave_type: string;
  leave_type_display: string;
  total_days: number;
  used_days: number;
  available_days: number;
}

interface LeaveRequest {
  id: string;
  leave_type_display: string;
  start_date: string;
  end_date: string;
  total_days: number;
  status: string;
}

const STATUS_BADGE: Record<string, string> = {
  pending:    "badge badge-warn",
  l2_pending: "badge badge-warn",
  approved:   "badge badge-success",
  rejected:   "badge badge-error",
  cancelled:  "badge badge-neutral",
};
const STATUS_LABEL: Record<string, string> = {
  pending:    "Pending",
  l2_pending: "Pending L2",
  approved:   "Approved",
  rejected:   "Rejected",
  cancelled:  "Cancelled",
};

const BALANCE_COLORS: Record<string, string> = {
  casual:    "var(--info)",
  earned:    "var(--success)",
  sick:      "var(--warn)",
  maternity: "var(--secondary)",
  paternity: "var(--primary)",
  lwp:       "var(--outline)",
};

function fmtDate(iso: string) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

export default function EmployeeDashboard({ session }: Props) {
  const firstName = session.name.split(" ")[0];
  const year = new Date().getFullYear();

  const { data: balRaw,  loading: balLoading } = useFetch<{ results: LeaveBalance[] }>(
    API.leave.balance + `?year=${year}`
  );
  const { data: reqRaw, loading: reqLoading } = useFetch<{ results: LeaveRequest[] }>(
    API.leave.requests
  );

  const requests       = reqRaw?.results ?? [];
  const balances       = balRaw?.results ?? [];
  const recentRequests = requests.slice(0, 5);
  const pendingCount   = requests.filter(r => r.status === "pending" || r.status === "l2_pending").length;
  const displayBals    = balances.filter(b => b.leave_type !== "lwp");

  return (
    <>
      {/* Greeting banner */}
      <div className="dash-greeting mb-20" style={{ background: "linear-gradient(135deg, #2d5a8e 0%, #1a3a6e 100%)", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 20 }}>
        <div className="dash-greeting-content">
          <h1>Welcome back, {firstName} 👋</h1>
          <p>Have a productive day!</p>
          <div className="dash-greeting-stats">
            <div className="dgs-item">
              <div className="dgs-val">{balLoading ? "—" : (balances ?? []).length}</div>
              <div className="dgs-lbl">Leave Types</div>
            </div>
            <div className="dgs-item">
              <div className="dgs-val">{reqLoading ? "—" : pendingCount}</div>
              <div className="dgs-lbl">Pending Requests</div>
            </div>
            <div className="dgs-item">
              <div className="dgs-val">{reqLoading ? "—" : (requests ?? []).filter(r => r.status === "approved").length}</div>
              <div className="dgs-lbl">Approved Leaves</div>
            </div>
            <div className="dgs-item">
              <div className="dgs-val">{year}</div>
              <div className="dgs-lbl">Leave Year</div>
            </div>
          </div>
        </div>
        <div style={{ flexShrink: 0, position: "relative", zIndex: 1 }}>
          <ClockInButton />
        </div>
      </div>

      {/* Quick actions */}
      <div className="card mb-20">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-bolt" /> Quick Actions</div>
        </div>
        <div className="card-body">
          <div className="qa-grid">
            {[
              { href: "/dashboard/leave",       icon: "ti-beach",       bg: "rgba(27,138,107,0.12)", color: "var(--success)", label: "Apply Leave"  },
              { href: "/dashboard/my-payslip",  icon: "ti-receipt",     bg: "rgba(30,78,140,0.12)",  color: "var(--primary)", label: "My Payslips"  },
              { href: "/dashboard/my-attendance",icon: "ti-clock",      bg: "rgba(14,124,134,0.12)", color: "var(--info)",    label: "Attendance"   },
              { href: "/dashboard/expenses",    icon: "ti-wallet",       bg: "rgba(181,101,29,0.12)", color: "var(--warn)",    label: "My Expenses"  },
              { href: "/dashboard/documents",   icon: "ti-folder",       bg: "rgba(30,78,140,0.12)",  color: "var(--primary)", label: "Documents"    },
              { href: "/dashboard/profile",     icon: "ti-user-circle",  bg: "rgba(14,124,134,0.12)", color: "var(--info)",    label: "My Profile"   },
            ].map(a => (
              <a key={a.href} href={a.href} className="qa-tile">
                <div className="qa-icon" style={{ background: a.bg, color: a.color }}>
                  <i className={`ti ${a.icon}`} />
                </div>
                <span className="qa-label">{a.label}</span>
              </a>
            ))}
          </div>
        </div>
      </div>

      <div className="grid-2">
        {/* Left */}
        <div>
          {/* Leave Balances */}
          <div className="card mb-16">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-beach" /> Leave Balances — {year}</div>
              <a href="/dashboard/leave" className="btn btn-ghost btn-sm">Apply Leave</a>
            </div>
            {balLoading ? (
              <div style={{ padding: "30px 24px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
                <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Loading…
              </div>
            ) : displayBals.length === 0 ? (
              <div style={{ padding: "24px", fontSize: 13, color: "var(--on-variant)", textAlign: "center" }}>
                No leave balance found for {year}. Contact HR to credit your leave.
              </div>
            ) : (
              <div style={{ padding: 0 }}>
                {displayBals.map(b => {
                  const avail = Number(b.available_days);
                  const total = Number(b.total_days);
                  const pct   = total > 0 ? Math.min(100, (avail / total) * 100) : 0;
                  const color = BALANCE_COLORS[b.leave_type] ?? "var(--primary)";
                  return (
                    <div key={b.leave_type} style={{ padding: "12px 20px", borderBottom: "1px solid var(--bg-high)" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 13 }}>
                        <span style={{ fontWeight: 500 }}>{b.leave_type_display}</span>
                        <span style={{ color: "var(--on-variant)" }}>{avail} / {total} days</span>
                      </div>
                      <div className="progress-bar">
                        <div className="progress-fill" style={{ width: `${pct}%`, background: color }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right */}
        <div>
          {/* My Recent Requests */}
          <div className="card mb-16">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-inbox" /> My Recent Requests</div>
              {pendingCount > 0 && <span className="badge badge-warn">{pendingCount} pending</span>}
            </div>
            {reqLoading ? (
              <div style={{ padding: "30px 24px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
                <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Loading…
              </div>
            ) : recentRequests.length === 0 ? (
              <div style={{ padding: "24px", fontSize: 13, color: "var(--on-variant)", textAlign: "center" }}>
                No leave requests yet. <a href="/dashboard/leave" style={{ color: "var(--primary)" }}>Apply your first leave.</a>
              </div>
            ) : (
              <div style={{ padding: 0 }}>
                {recentRequests.map(r => (
                  <div key={r.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 20px", borderBottom: "1px solid var(--bg-high)" }}>
                    <div className="qa-icon" style={{ background: "var(--bg-low)", color: "var(--success)", width: 34, height: 34, fontSize: 15, flexShrink: 0 }}>
                      <i className="ti ti-beach" />
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, fontWeight: 500 }}>{r.leave_type_display} — {r.total_days} day{r.total_days !== 1 ? "s" : ""}</div>
                      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{fmtDate(r.start_date)} – {fmtDate(r.end_date)}</div>
                    </div>
                    <span className={STATUS_BADGE[r.status] ?? "badge badge-neutral"}>{STATUS_LABEL[r.status] ?? r.status}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Upcoming Events */}
          <div className="card">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-calendar" /> Quick Links</div>
            </div>
            <div className="card-body">
              <div className="qa-grid" style={{ gridTemplateColumns: "repeat(2, 1fr)" }}>
                {[
                  { href: "/dashboard/leave",        icon: "ti-beach",       label: "Leave History"  },
                  { href: "/dashboard/my-attendance", icon: "ti-clock",       label: "My Attendance"  },
                  { href: "/dashboard/expenses",     icon: "ti-wallet",       label: "Claim Expense"  },
                  { href: "/dashboard/documents",    icon: "ti-file-text",    label: "My Documents"   },
                ].map(a => (
                  <a key={a.href} href={a.href} style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 12px", borderRadius: 8, background: "var(--bg-low)", textDecoration: "none", fontSize: 13, color: "var(--on-bg)", fontWeight: 500 }}>
                    <i className={`ti ${a.icon}`} style={{ fontSize: 16, color: "var(--primary)" }} />
                    {a.label}
                  </a>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
