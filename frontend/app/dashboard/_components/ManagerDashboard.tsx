"use client";

import ClockInButton from "@/components/ClockInButton";
import AnnouncementCard from "@/components/dashboard/AnnouncementCard";
import { TeamProvider, useTeam } from "@/lib/teamContext";
import type { SessionPayload } from "@/lib/session";

interface Props { session: SessionPayload }

const QA_META: Record<string, { icon: string; bg: string; color: string }> = {
  apply_leave:      { icon: "ti-beach",       bg: "rgba(27,138,107,0.12)", color: "var(--success)" },
  my_requests:      { icon: "ti-inbox",        bg: "rgba(181,101,29,0.12)", color: "var(--warn)"    },
  team_members:     { icon: "ti-users",        bg: "rgba(14,124,134,0.12)", color: "var(--info)"    },
  review_approvals: { icon: "ti-checks",       bg: "rgba(181,101,29,0.12)", color: "var(--warn)"    },
  my_payslip:       { icon: "ti-receipt",      bg: "rgba(30,78,140,0.12)",  color: "var(--primary)" },
  interviews:       { icon: "ti-user-search",  bg: "rgba(30,78,140,0.12)",  color: "var(--primary)" },
};

const APPROVAL_META: Record<string, { icon: string; color: string; bg: string }> = {
  leave:                 { icon: "ti-beach",   color: "var(--primary)", bg: "rgba(30,78,140,0.12)"  },
  expense:               { icon: "ti-receipt", color: "var(--warn)",    bg: "rgba(181,101,29,0.12)" },
  attendance_correction: { icon: "ti-clock",   color: "#D97706",        bg: "rgba(217,119,6,0.12)"  },
};

const ATTENDANCE_BADGE: Record<string, string> = {
  present:    "badge badge-success",
  late:       "badge badge-warn",
  half_day:   "badge badge-primary",
  incomplete: "badge badge-neutral",
  on_leave:   "badge badge-info",
  weekly_off: "badge badge-neutral",
  holiday:    "badge badge-neutral",
  absent:     "badge badge-error",
};

const LEAVE_STATUS_BADGE: Record<string, string> = {
  approved:   "badge badge-success",
  pending:    "badge badge-warn",
  l2_pending: "badge badge-warn",
};

const ACTIVITY_ICON: Record<string, { icon: string; cls: string }> = {
  login:                        { icon: "ti-login",      cls: "tl-info"    },
  logout:                       { icon: "ti-logout",     cls: "tl-neutral" },
  leave_apply:                  { icon: "ti-beach",      cls: "tl-warn"    },
  leave_approved:               { icon: "ti-check",      cls: "tl-success" },
  leave_rejected:               { icon: "ti-x",          cls: "tl-error"   },
  leave_cancelled:              { icon: "ti-ban",        cls: "tl-neutral" },
  expense_submitted:            { icon: "ti-receipt",    cls: "tl-warn"    },
  expense_approved:             { icon: "ti-check",      cls: "tl-success" },
  attendance_correction_submit: { icon: "ti-clock-edit", cls: "tl-info"    },
  clock_in:                     { icon: "ti-login-2",    cls: "tl-success" },
  clock_out:                    { icon: "ti-logout-2",   cls: "tl-neutral" },
};

function initials(name: string): string {
  return name.split(" ").map(w => w[0] ?? "").join("").toUpperCase().slice(0, 2);
}

function timeAgo(iso: string): string {
  const m = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export default function ManagerDashboard({ session }: Props) {
  return (
    <TeamProvider>
      <ManagerDashboardInner session={session} />
    </TeamProvider>
  );
}

function ManagerDashboardInner({ session }: Props) {
  const { data, loading } = useTeam();

  const ov      = data?.team_overview;
  const actions = data?.quick_actions        ?? [];
  const pending = data?.pending_approvals    ?? [];
  const activity= data?.recent_team_activity ?? [];
  const todayBd = data?.todays_birthdays     ?? [];
  const upcomBd = data?.upcoming_birthdays   ?? [];
  const teamAtt = data?.team_attendance      ?? [];
  const leaves  = data?.upcoming_leaves      ?? [];

  const presentCount = teamAtt.filter(a => a.status === "present" || a.status === "late").length;

  return (
    <>
      {/* Manager Console */}
      <div className="mb-20" style={{ background: "linear-gradient(135deg, #1a3a6e 0%, #0e2447 100%)", borderRadius: 10, overflow: "hidden", position: "relative" }}>
        <div style={{ position: "absolute", top: -50, right: -50, width: 180, height: 180, borderRadius: "50%", border: "1px solid rgba(255,255,255,0.06)", pointerEvents: "none" }} />
        <div style={{ position: "absolute", top: -20, right: -20, width: 110, height: 110, borderRadius: "50%", border: "1px solid rgba(255,255,255,0.04)", pointerEvents: "none" }} />

        {/* Top bar */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 16px 0", position: "relative", flexWrap: "wrap", gap: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 28, height: 28, borderRadius: 6, background: "rgba(255,255,255,0.10)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, color: "#fff", flexShrink: 0 }}>
              <i className="ti ti-users-group" />
            </div>
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", color: "rgba(255,255,255,0.5)", textTransform: "uppercase", lineHeight: 1 }}>Team Console</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#fff", lineHeight: 1.2 }}>
                {ov ? `${ov.greeting}, ${ov.manager_name.split(" ")[0]}` : `Hello, ${session.name.split(" ")[0]}`}
              </div>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {ov && (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 20, background: "rgba(255,255,255,0.10)", color: "rgba(255,255,255,0.85)", border: "1px solid rgba(255,255,255,0.15)" }}>
                <i className="ti ti-chart-bar" style={{ fontSize: 11 }} />
                {ov.team_attendance_percentage}% Attendance
              </span>
            )}
            <ClockInButton />
          </div>
        </div>

        <div style={{ margin: "6px 16px 0", borderBottom: "1px solid rgba(255,255,255,0.08)" }} />

        {/* Stats grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)" }}>
          {[
            { icon: "ti-users",        val: ov ? String(ov.team_size)               : (loading ? "—" : "0"), lbl: "Team Size",         sub: "Active direct reports" },
            { icon: "ti-checks",       val: ov ? String(ov.pending_approvals)        : (loading ? "—" : "0"), lbl: "Pending Approvals", sub: "Awaiting review"       },
            { icon: "ti-beach",        val: ov ? String(ov.employees_on_leave_today) : (loading ? "—" : "0"), lbl: "On Leave Today",    sub: "Team members"          },
            { icon: "ti-calendar",     val: ov ? `${ov.team_attendance_percentage}%` : (loading ? "—" : "—"), lbl: "Attendance Rate",   sub: "Today"                 },
          ].map(stat => (
            <div key={stat.lbl} style={{ padding: "8px 14px", display: "flex", flexDirection: "column", gap: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <i className={`ti ${stat.icon}`} style={{ fontSize: 12, color: "rgba(255,255,255,0.4)" }} />
                <span style={{ fontSize: 18, fontWeight: 800, color: "#fff", lineHeight: 1 }}>{stat.val}</span>
              </div>
              <div style={{ fontSize: 11, fontWeight: 600, color: "rgba(255,255,255,0.72)" }}>{stat.lbl}</div>
              <div style={{ fontSize: 10, color: "rgba(255,255,255,0.36)" }}>{stat.sub}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Announcement */}
      <AnnouncementCard />

      {/* Quick actions */}
      {actions.length > 0 && (
        <div className="card mb-20">
          <div className="card-header"><div className="card-title"><i className="ti ti-bolt" /> Quick Actions</div></div>
          <div className="card-body">
            <div className="qa-grid">
              {actions.map(action => {
                const meta = QA_META[action.id] ?? { icon: "ti-link", bg: "var(--bg-low)", color: "var(--primary)" };
                return (
                  <a key={action.id} href={action.url} className="qa-tile" style={{ position: "relative" }}>
                    <div className="qa-icon" style={{ background: meta.bg, color: meta.color }}>
                      <i className={`ti ${meta.icon}`} />
                    </div>
                    <span className="qa-label">{action.label}</span>
                    {action.count !== null && action.count > 0 && (
                      <span style={{ position: "absolute", top: 4, right: 4, background: "var(--error)", color: "#fff", borderRadius: 10, fontSize: 10, fontWeight: 700, padding: "1px 5px", lineHeight: 1.4 }}>
                        {action.count}
                      </span>
                    )}
                  </a>
                );
              })}
            </div>
          </div>
        </div>
      )}

      <div className="grid-2">
        {/* Left column */}
        <div>
          {/* Pending Approvals */}
          <div className="card mb-16">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-checks" /> Pending Approvals</div>
              {pending.length > 0 && <span className="badge badge-warn">{pending.length} item{pending.length !== 1 ? "s" : ""}</span>}
            </div>
            {pending.length === 0 ? (
              <div className="card-body" style={{ color: "var(--on-variant)", fontSize: 13 }}>{loading ? "Loading…" : "No pending approvals."}</div>
            ) : (
              <div style={{ padding: 0 }}>
                {pending.map(item => {
                  const meta = APPROVAL_META[item.approval_type] ?? APPROVAL_META.leave;
                  return (
                    <div key={item.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 20px", borderBottom: "1px solid var(--bg-high)" }}>
                      <div className="qa-icon" style={{ background: meta.bg, color: meta.color, width: 36, height: 36, fontSize: 16, flexShrink: 0 }}>
                        <i className={`ti ${meta.icon}`} />
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {item.employee_name} <span style={{ fontSize: 11, color: "var(--on-variant)", fontWeight: 400 }}>({item.employee_id})</span>
                        </div>
                        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{item.summary} · Applied {fmtDate(item.applied_on)}</div>
                      </div>
                      <a href="/dashboard/approvals" className="btn btn-ghost btn-sm" style={{ flexShrink: 0, fontSize: 11 }}>Review</a>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Recent Team Activity */}
          <div className="card">
            <div className="card-header"><div className="card-title"><i className="ti ti-activity" /> Recent Team Activity</div></div>
            <div className="card-body">
              {activity.length === 0 ? (
                <div style={{ color: "var(--on-variant)", fontSize: 13 }}>{loading ? "Loading…" : "No recent activity."}</div>
              ) : (
                <>
                  <div className="timeline">
                    {activity.map((item, idx) => {
                      const meta = ACTIVITY_ICON[item.action] ?? { icon: "ti-point", cls: "tl-neutral" };
                      return (
                        <div key={idx} className="tl-item">
                          <div className={`tl-dot ${meta.cls}`}><i className={`ti ${meta.icon}`} /></div>
                          <div className="tl-body">
                            <div className="tl-title">{item.employee_name} — {item.description}</div>
                            <div className="tl-time">{timeAgo(item.created_at)}</div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Right column */}
        <div>
          {/* Birthdays */}
          {(todayBd.length > 0 || upcomBd.length > 0) && (
            <div className="card mb-16">
              <div className="card-header"><div className="card-title"><i className="ti ti-cake" /> Birthdays</div></div>
              {todayBd.length > 0 && (
                <div style={{ padding: "10px 20px 0" }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 }}>Today</div>
                  {todayBd.map(b => (
                    <div key={b.employee_id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", borderBottom: "1px solid var(--bg-high)" }}>
                      <div style={{ width: 32, height: 32, borderRadius: "50%", background: "rgba(27,138,107,0.15)", color: "var(--success)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, flexShrink: 0 }}>{initials(b.full_name)}</div>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 500 }}>{b.full_name} 🎂</div>
                        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{b.department}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {upcomBd.length > 0 && (
                <div style={{ padding: "10px 20px" }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 }}>Upcoming (30 days)</div>
                  {upcomBd.slice(0, 5).map(b => (
                    <div key={b.employee_id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "7px 0", borderBottom: "1px solid var(--bg-high)" }}>
                      <div style={{ width: 30, height: 30, borderRadius: "50%", background: "var(--bg-low)", color: "var(--primary)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, flexShrink: 0 }}>{initials(b.full_name)}</div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 13, fontWeight: 500 }}>{b.full_name}</div>
                        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{b.department}</div>
                      </div>
                      <div style={{ fontSize: 11, color: "var(--on-variant)", whiteSpace: "nowrap" }}>in {b.days_until}d</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Team Attendance Today */}
          <div className="card mb-16">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-users" /> Team Attendance Today</div>
              {ov && <span className="badge badge-success">{presentCount}/{ov.team_size} present</span>}
            </div>
            {teamAtt.length === 0 ? (
              <div className="card-body" style={{ color: "var(--on-variant)", fontSize: 13 }}>{loading ? "Loading…" : "No attendance data."}</div>
            ) : (
              <div style={{ padding: 0, maxHeight: 340, overflowY: "auto" }}>
                {teamAtt.map(emp => (
                  <div key={emp.employee_id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 20px", borderBottom: "1px solid var(--bg-high)" }}>
                    <div style={{ width: 30, height: 30, borderRadius: "50%", background: "var(--primary)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 600, flexShrink: 0 }}>{initials(emp.employee_name)}</div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{emp.employee_name}</div>
                      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{emp.designation} · {emp.clock_in ?? "—"}</div>
                    </div>
                    <span className={ATTENDANCE_BADGE[emp.status] ?? "badge badge-neutral"} style={{ flexShrink: 0, textTransform: "capitalize" }}>
                      {emp.status.replace(/_/g, " ")}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Upcoming Leaves */}
          <div className="card">
            <div className="card-header"><div className="card-title"><i className="ti ti-calendar" /> Upcoming Leaves</div></div>
            {leaves.length === 0 ? (
              <div className="card-body" style={{ color: "var(--on-variant)", fontSize: 13 }}>{loading ? "Loading…" : "No upcoming leaves."}</div>
            ) : (
              <div style={{ padding: 0 }}>
                {leaves.map(lv => (
                  <div key={lv.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 20px", borderBottom: "1px solid var(--bg-high)" }}>
                    <div style={{ width: 32, height: 32, borderRadius: "50%", background: "var(--bg-low)", color: "var(--primary)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 600, flexShrink: 0 }}>{initials(lv.employee_name)}</div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, fontWeight: 500 }}>{lv.employee_name}</div>
                      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{lv.leave_type} · {fmtDate(lv.date_from)} – {fmtDate(lv.date_to)} ({lv.total_days}d)</div>
                    </div>
                    <span className={LEAVE_STATUS_BADGE[lv.status] ?? "badge badge-neutral"} style={{ flexShrink: 0, textTransform: "capitalize" }}>
                      {lv.status.replace(/_/g, " ")}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
