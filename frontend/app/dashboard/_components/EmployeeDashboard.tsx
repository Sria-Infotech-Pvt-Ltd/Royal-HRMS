import type { SessionPayload } from "@/lib/session";
import ClockInButton from "@/components/ClockInButton";

interface Props { session: SessionPayload }

export default function EmployeeDashboard({ session }: Props) {
  const firstName = session.name.split(" ")[0];

  return (
    <>
      {/* Greeting banner */}
      <div className="dash-greeting mb-20" style={{ background: "linear-gradient(135deg, #2d5a8e 0%, #1a3a6e 100%)", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 20 }}>
        <div className="dash-greeting-content">
          <h1>Welcome back, {firstName} 👋</h1>
          <p>Monday, June 24, 2026 · Have a great day!</p>
          <div className="dash-greeting-stats">
            <div className="dgs-item"><div className="dgs-val">22</div><div className="dgs-lbl">Days Present</div></div>
            <div className="dgs-item"><div className="dgs-val">8</div><div className="dgs-lbl">Leave Balance</div></div>
            <div className="dgs-item"><div className="dgs-val">2</div><div className="dgs-lbl">Pending Requests</div></div>
            <div className="dgs-item"><div className="dgs-val">Jun</div><div className="dgs-lbl">Latest Payslip</div></div>
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
              { href: "/dashboard/leave",        icon: "ti-beach",        bg: "rgba(27,138,107,0.12)", color: "var(--success)", label: "Apply Leave"   },
              { href: "/dashboard/my-payslip",   icon: "ti-receipt",      bg: "rgba(30,78,140,0.12)",  color: "var(--primary)", label: "My Payslips"   },
              { href: "/dashboard/attendance",   icon: "ti-clock",        bg: "rgba(14,124,134,0.12)", color: "var(--info)",    label: "Attendance"    },
              { href: "/dashboard/expenses",     icon: "ti-wallet",       bg: "rgba(181,101,29,0.12)", color: "var(--warn)",    label: "My Expenses"   },
              { href: "/dashboard/documents",    icon: "ti-folder",       bg: "rgba(30,78,140,0.12)",  color: "var(--primary)", label: "Documents"     },
              { href: "/dashboard/profile",      icon: "ti-user-circle",  bg: "rgba(14,124,134,0.12)", color: "var(--info)",    label: "My Profile"    },
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
          {/* Attendance this month */}
          <div className="card mb-16">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-clock" /> Attendance — June 2026</div>
            </div>
            <div className="card-body">
              <div className="stats-grid" style={{ gridTemplateColumns:"1fr 1fr", marginBottom:0 }}>
                <div className="stat-card" style={{ padding:14 }}>
                  <div className="stat-label">Present</div>
                  <div className="stat-value" style={{ fontSize:22 }}>22</div>
                  <div className="stat-sub">days</div>
                </div>
                <div className="stat-card" style={{ padding:14 }}>
                  <div className="stat-label">Absent</div>
                  <div className="stat-value" style={{ fontSize:22, color:"var(--error)" }}>1</div>
                  <div className="stat-sub">days</div>
                </div>
                <div className="stat-card" style={{ padding:14 }}>
                  <div className="stat-label">Late Arrivals</div>
                  <div className="stat-value" style={{ fontSize:22, color:"var(--warn)" }}>2</div>
                  <div className="stat-sub">days</div>
                </div>
                <div className="stat-card" style={{ padding:14 }}>
                  <div className="stat-label">On Leave</div>
                  <div className="stat-value" style={{ fontSize:22, color:"var(--info)" }}>1</div>
                  <div className="stat-sub">days</div>
                </div>
              </div>
            </div>
          </div>

          {/* Leave balances */}
          <div className="card">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-beach" /> Leave Balances</div>
              <a href="/dashboard/leave" className="btn btn-ghost btn-sm">Apply Leave</a>
            </div>
            <div style={{ padding: 0 }}>
              {[
                { type: "Earned Leave",   balance: 8,  total: 15, color: "var(--success)" },
                { type: "Sick Leave",     balance: 5,  total: 12, color: "var(--warn)"    },
                { type: "Casual Leave",   balance: 3,  total: 6,  color: "var(--info)"    },
              ].map(l => (
                <div key={l.type} style={{ padding:"12px 20px", borderBottom:"1px solid var(--bg-high)" }}>
                  <div style={{ display:"flex",justifyContent:"space-between",marginBottom:6,fontSize:13 }}>
                    <span style={{ fontWeight:500 }}>{l.type}</span>
                    <span style={{ color:"var(--on-variant)" }}>{l.balance} / {l.total} days</span>
                  </div>
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width:`${(l.balance / l.total) * 100}%`, background: l.color }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right */}
        <div>
          {/* My Requests */}
          <div className="card mb-16">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-inbox" /> My Recent Requests</div>
              <span className="badge badge-warn">2 pending</span>
            </div>
            <div style={{ padding: 0 }}>
              {[
                { icon: "ti-beach",  color:"var(--success)", title:"Earned Leave — 2 days",   date:"Jun 30 – Jul 1",  status:"Pending",  badge:"badge-warn"    },
                { icon: "ti-wallet", color:"var(--warn)",    title:"Expense Claim — ₹2,200",  date:"Jun 20",          status:"Pending",  badge:"badge-warn"    },
                { icon: "ti-beach",  color:"var(--success)", title:"Sick Leave — 1 day",      date:"Jun 5",           status:"Approved", badge:"badge-success" },
              ].map((r, i) => (
                <div key={i} style={{ display:"flex",alignItems:"center",gap:12,padding:"12px 20px",borderBottom:"1px solid var(--bg-high)" }}>
                  <div className="qa-icon" style={{ background:"var(--bg-low)",color:r.color,width:34,height:34,fontSize:15,flexShrink:0 }}>
                    <i className={`ti ${r.icon}`} />
                  </div>
                  <div style={{ flex:1 }}>
                    <div style={{ fontSize:13,fontWeight:500 }}>{r.title}</div>
                    <div style={{ fontSize:11,color:"var(--on-variant)" }}>{r.date}</div>
                  </div>
                  <span className={`badge ${r.badge}`}>{r.status}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Upcoming */}
          <div className="card">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-calendar" /> Upcoming Events</div>
            </div>
            <div className="card-body">
              <div className="timeline">
                <div className="tl-item">
                  <div className="tl-dot tl-info"><i className="ti ti-report-money" /></div>
                  <div className="tl-body"><div className="tl-title">June payslip available</div><div className="tl-time">Jul 1, 2026</div></div>
                </div>
                <div className="tl-item">
                  <div className="tl-dot tl-success"><i className="ti ti-cake" /></div>
                  <div className="tl-body"><div className="tl-title">Team birthday — Meena Iyer</div><div className="tl-time">Jun 24, 2026</div></div>
                </div>
                <div className="tl-item">
                  <div className="tl-dot tl-warn"><i className="ti ti-calendar-event" /></div>
                  <div className="tl-body"><div className="tl-title">Company all-hands meeting</div><div className="tl-time">Jun 28, 2026</div></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
