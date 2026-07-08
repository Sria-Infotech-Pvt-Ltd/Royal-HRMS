import type { SessionPayload } from "@/lib/session";
import BirthdayWidget from "@/components/dashboard/BirthdayWidget";

interface Props { session: SessionPayload }

export default function AdminDashboard({ session }: Props) {
  const firstName = session.name.split(" ")[0];

  return (
    <>
      {/* Greeting banner */}
      <div className="dash-greeting mb-20" style={{ background: "linear-gradient(135deg, #1a3a6e 0%, #0e2447 100%)" }}>
        <div className="dash-greeting-content">
          <h1>System Console, {firstName} 🛠️</h1>
          <p>All systems operational · Last backup 2 hours ago · 6 active sessions</p>
          <div className="dash-greeting-stats">
            <div className="dgs-item"><div className="dgs-val">99.9%</div><div className="dgs-lbl">Uptime (30d)</div></div>
            <div className="dgs-item"><div className="dgs-val">6</div><div className="dgs-lbl">Active Users</div></div>
            <div className="dgs-item"><div className="dgs-val">2.4 GB</div><div className="dgs-lbl">Storage Used</div></div>
            <div className="dgs-item"><div className="dgs-val">0</div><div className="dgs-lbl">Critical Alerts</div></div>
          </div>
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
              { href: "/dashboard/employees", icon: "ti-id-badge", bg: "rgba(30,78,140,0.12)", color: "var(--primary)", label: "Employees" },
              { href: "/dashboard/settings/permissions", icon: "ti-shield-check", bg: "rgba(27,138,107,0.12)", color: "var(--success)", label: "Roles & Perms" },
              { href: "/dashboard/attendance", icon: "ti-clock", bg: "rgba(14,124,134,0.12)", color: "var(--info)", label: "Attendance" },
              { href: "/dashboard/payroll", icon: "ti-report-money", bg: "rgba(181,101,29,0.12)", color: "var(--warn)", label: "Payroll" },
              { href: "/dashboard/branches", icon: "ti-building-skyscraper", bg: "rgba(30,78,140,0.12)", color: "var(--primary)", label: "Branches" },
              { href: "/dashboard/settings", icon: "ti-settings", bg: "rgba(181,101,29,0.12)", color: "var(--warn)", label: "Settings" },
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
          {/* Module Health */}
          <div className="card mb-16">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-stack-2" /> Module Health</div>
            </div>
            <div className="card-body">
              <div className="health-grid">
                {[
                  { name: "Recruitment", status: "operational", meta: "156 events / day", dot: "" },
                  { name: "Payroll", status: "operational", meta: "Last run: Jun 30", dot: "" },
                  { name: "Attendance", status: "operational", meta: "186 punches today", dot: "" },
                  { name: "Leave Mgmt", status: "warn", meta: "2 pending approvals", dot: "warn" },
                  { name: "Documents", status: "operational", meta: "All synced", dot: "" },
                  { name: "Email", status: "warn", meta: "SMTP test needed", dot: "warn" },
                ].map(m => (
                  <div key={m.name} className="health-item">
                    <div className="health-row">
                      <span className="health-name">{m.name}</span>
                      <span className={`health-dot${m.dot ? " " + m.dot : ""}`} />
                    </div>
                    <div className="health-meta">{m.meta}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Organisation Headcount */}
          <div className="card">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-chart-donut" /> Department Headcount</div>
            </div>
            <div className="card-body" style={{ display: "flex", alignItems: "center", gap: 24, flexWrap: "wrap" }}>
              <div className="donut-chart" style={{ background: "conic-gradient(var(--primary) 0% 30%, var(--success) 30% 50%, var(--info) 50% 68%, var(--warn) 68% 82%, var(--secondary) 82% 100%)" }}>
                <div className="donut-chart-inner">
                  <div className="donut-val">142</div>
                  <div className="donut-lbl">Total</div>
                </div>
              </div>
              <div style={{ flex: 1, minWidth: 140 }}>
                {[["Engineering", "43", "var(--primary)"], ["HR", "28", "var(--success)"], ["Finance", "25", "var(--info)"], ["Sales", "20", "var(--warn)"], ["IT", "26", "var(--secondary)"]].map(([d, c, col]) => (
                  <div key={d} style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 0", fontSize: 12 }}>
                    <span style={{ width: 10, height: 10, borderRadius: 2, background: col, flexShrink: 0 }} />
                    <span style={{ flex: 1 }}>{d}</span>
                    <strong>{c}</strong>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right */}
        <div>
          <BirthdayWidget />
          {/* Recent System Events */}
          <div className="card mb-16">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-shield-lock" /> Recent System Events</div>
            </div>
            <div className="card-body">
              <div className="timeline">
                <div className="tl-item">
                  <div className="tl-dot tl-success"><i className="ti ti-lock" /></div>
                  <div className="tl-body"><div className="tl-title">Roles & permissions updated</div><div className="tl-time">Today, 11:20 AM</div></div>
                </div>
                <div className="tl-item">
                  <div className="tl-dot tl-info"><i className="ti ti-database" /></div>
                  <div className="tl-body"><div className="tl-title">Database backup completed</div><div className="tl-time">Today, 2:00 AM</div></div>
                </div>
                <div className="tl-item">
                  <div className="tl-dot tl-warn"><i className="ti ti-mail" /></div>
                  <div className="tl-body"><div className="tl-title">SMTP configuration needs verification</div><div className="tl-time">Jun 10, 9:15 AM</div></div>
                </div>
                <div className="tl-item">
                  <div className="tl-dot tl-neutral"><i className="ti ti-user" /></div>
                  <div className="tl-body"><div className="tl-title">New user account created: priya.sharma</div><div className="tl-time">Jun 8, 10:00 AM</div></div>
                </div>
              </div>
            </div>
          </div>

          {/* Active Sessions */}
          <div className="card">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-users" /> Active Sessions</div>
              <span className="badge badge-success">6 online</span>
            </div>
            <div style={{ padding: 0 }}>
              {[
                { initials: "HA", name: "HR Admin", role: "hr_admin", time: "2 min ago" },
                { initials: "SA", name: "System Admin", role: "system_admin", time: "Now" },
                { initials: "AM", name: "Arjun Mehta", role: "manager", time: "5 min ago" },
                { initials: "PS", name: "Priya Sharma", role: "employee", time: "12 min ago" },
              ].map(u => (
                <div key={u.name} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 20px", borderBottom: "1px solid var(--bg-high)" }}>
                  <div style={{ width: 32, height: 32, borderRadius: "50%", background: "var(--primary)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 600, flexShrink: 0 }}>{u.initials}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{u.name}</div>
                    <code style={{ fontSize: 10, color: "var(--on-variant)" }}>{u.role}</code>
                  </div>
                  <span style={{ fontSize: 11, color: "var(--outline)" }}>{u.time}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
