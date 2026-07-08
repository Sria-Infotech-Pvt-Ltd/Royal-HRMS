import type { SessionPayload } from "@/lib/session";
import ClockInButton    from "@/components/ClockInButton";
import BirthdayWidget   from "@/components/dashboard/BirthdayWidget";

interface Props { session: SessionPayload }

export default function HRDashboard({ session }: Props) {
  const firstName = session.name.split(" ")[0];

  return (
    <>
      {/* Greeting banner */}
      <div className="dash-greeting mb-20" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 20 }}>
        <div className="dash-greeting-content">
          <h1>Good morning, {firstName} 👋</h1>
          <p>4 candidates in pipeline · 2 leave approvals pending · 2 birthdays today</p>
          <div className="dash-greeting-stats">
            <div className="dgs-item"><div className="dgs-val">142</div><div className="dgs-lbl">Total Workforce</div></div>
            <div className="dgs-item"><div className="dgs-val">6</div><div className="dgs-lbl">Pending Actions</div></div>
            <div className="dgs-item"><div className="dgs-val">4</div><div className="dgs-lbl">Active Interviews</div></div>
            <div className="dgs-item"><div className="dgs-val">₹12.4L</div><div className="dgs-lbl">June Payroll</div></div>
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
              { href: "/dashboard/interview-list",   icon: "ti-users",        bg: "rgba(30,78,140,0.12)",  color: "var(--primary)", label: "Interview List"  },
              { href: "/dashboard/leave",             icon: "ti-beach",        bg: "rgba(27,138,107,0.12)", color: "var(--success)", label: "Leave Approvals" },
              { href: "/dashboard/payroll",           icon: "ti-report-money", bg: "rgba(181,101,29,0.12)", color: "var(--warn)",    label: "Run Payroll"     },
              { href: "/dashboard/employees",         icon: "ti-id-badge",     bg: "rgba(14,124,134,0.12)", color: "var(--info)",    label: "Employees"       },
              { href: "/dashboard/candidate-review",  icon: "ti-user-check",   bg: "rgba(181,101,29,0.12)", color: "var(--warn)",    label: "Review Candidates" },
              { href: "/dashboard/settings",          icon: "ti-settings",     bg: "rgba(30,78,140,0.12)",  color: "var(--primary)", label: "Settings"        },
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

      {/* Two-column layout */}
      <div className="grid-2">

        {/* Left */}
        <div>
          {/* HR Action Queue */}
          <div className="card mb-16">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-inbox" /> HR Action Queue</div>
              <span className="badge badge-warn">6 items</span>
            </div>
            <div style={{ padding: 0 }}>
              {[
                { icon: "ti-user-check", bg: "rgba(181,101,29,0.12)", color: "var(--warn)",    title: "2 candidate reviews pending",       sub: "Selected candidates have submitted details",    href: "/dashboard/candidate-review" },
                { icon: "ti-beach",      bg: "rgba(27,138,107,0.12)", color: "var(--success)", title: "2 leave approvals pending",          sub: "Including 5-day EL request from Meena Iyer",   href: "/dashboard/leave"            },
                { icon: "ti-logout",     bg: "rgba(192,57,43,0.12)",  color: "var(--error)",   title: "1 separation in notice period",      sub: "Suresh Kumar — FnF pending",                   href: "/dashboard/separation"       },
                { icon: "ti-mail",       bg: "rgba(14,124,134,0.12)", color: "var(--info)",    title: "SMTP test recommended",              sub: "Last verified 14 days ago",                    href: "/dashboard/settings"         },
              ].map(item => (
                <a key={item.href} href={item.href} style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 20px", borderBottom: "1px solid var(--bg-high)", cursor: "pointer", textDecoration: "none" }}>
                  <div className="qa-icon" style={{ background: item.bg, color: item.color, width: 36, height: 36, fontSize: 16 }}>
                    <i className={`ti ${item.icon}`} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>{item.title}</div>
                    <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{item.sub}</div>
                  </div>
                  <i className="ti ti-chevron-right" style={{ color: "var(--outline)" }} />
                </a>
              ))}
            </div>
          </div>

          <BirthdayWidget />
        </div>

        {/* Right */}
        <div>
          {/* Recruitment Funnel */}
          <div className="card mb-16">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-filter" /> Recruitment Funnel — June</div>
              <a href="/dashboard/interview-list" className="btn btn-ghost btn-sm">View all</a>
            </div>
            <div className="card-body">
              <div className="funnel">
                <div className="funnel-stage">Interviews Scheduled <span className="funnel-val">12</span></div>
                <div className="funnel-stage">Interviewed <span className="funnel-val">9</span></div>
                <div className="funnel-stage">Selected <span className="funnel-val">5</span></div>
                <div className="funnel-stage">Details Submitted <span className="funnel-val">3</span></div>
                <div className="funnel-stage">Onboarded <span className="funnel-val">2</span></div>
              </div>
            </div>
          </div>

          {/* Department Headcount (CSS donut) */}
          <div className="card mb-16">
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
                {[
                  ["Engineering",  "43", "var(--primary)"],
                  ["HR",           "28", "var(--success)"],
                  ["Finance",      "25", "var(--info)"],
                  ["Sales",        "20", "var(--warn)"],
                  ["IT",           "26", "var(--secondary)"],
                ].map(([dept, count, color]) => (
                  <div key={dept} style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 0", fontSize: 12 }}>
                    <span style={{ width: 10, height: 10, borderRadius: 2, background: color, flexShrink: 0 }} />
                    <span style={{ flex: 1 }}>{dept}</span>
                    <strong>{count}</strong>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Live HR Activity */}
          <div className="card">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-activity" /> Live HR Activity</div>
            </div>
            <div className="card-body">
              <div className="timeline">
                <div className="tl-item">
                  <div className="tl-dot tl-success"><i className="ti ti-user-plus" /></div>
                  <div className="tl-body">
                    <div className="tl-title">Priya Sharma onboarded successfully</div>
                    <div className="tl-time">Today, 9:00 AM</div>
                  </div>
                </div>
                <div className="tl-item">
                  <div className="tl-dot tl-info"><i className="ti ti-mail" /></div>
                  <div className="tl-body">
                    <div className="tl-title">Selection email sent to Priya Sharma</div>
                    <div className="tl-time">Jun 10, 3:32 PM</div>
                  </div>
                </div>
                <div className="tl-item">
                  <div className="tl-dot tl-warn"><i className="ti ti-beach" /></div>
                  <div className="tl-body">
                    <div className="tl-title">Meena Iyer applied for 5-day Earned Leave</div>
                    <div className="tl-time">Jun 8, 11:00 AM</div>
                  </div>
                </div>
                <div className="tl-item">
                  <div className="tl-dot tl-neutral"><i className="ti ti-user-circle" /></div>
                  <div className="tl-body">
                    <div className="tl-title">Arjun Mehta updated emergency contact</div>
                    <div className="tl-time">Jun 5, 2:15 PM</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
