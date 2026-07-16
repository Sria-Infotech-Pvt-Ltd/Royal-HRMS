import type { SessionPayload } from "@/lib/session";
import BirthdayWidget from "@/components/dashboard/BirthdayWidget";

interface Props { session: SessionPayload }

export default function ManagerDashboard({ session }: Props) {
  const firstName = session.name.split(" ")[0];

  return (
    <>
      {/* Greeting banner */}
      <div className="dash-greeting mb-20" style={{ background: "linear-gradient(135deg, #0F6E56 0%, #0a4f3e 100%)" }}>
        <div className="dash-greeting-content">
          <h1>Team Overview, {firstName} 👋</h1>
          <p>3 approvals pending · 2 team members on leave today · Monday, Jun 24</p>
          <div className="dash-greeting-stats">
            <div className="dgs-item"><div className="dgs-val">12</div><div className="dgs-lbl">Team Size</div></div>
            <div className="dgs-item"><div className="dgs-val">3</div><div className="dgs-lbl">Pending Approvals</div></div>
            <div className="dgs-item"><div className="dgs-val">2</div><div className="dgs-lbl">On Leave Today</div></div>
            <div className="dgs-item"><div className="dgs-val">94%</div><div className="dgs-lbl">Attendance Rate</div></div>
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
              { href: "/dashboard/approvals",       icon: "ti-checks",        bg: "rgba(181,101,29,0.12)", color: "var(--warn)",    label: "Review Approvals"  },
              { href: "/dashboard/leave",            icon: "ti-beach",         bg: "rgba(27,138,107,0.12)", color: "var(--success)", label: "Apply Leave"       },
              { href: "/dashboard/my-payslip",       icon: "ti-receipt",       bg: "rgba(30,78,140,0.12)",  color: "var(--primary)", label: "My Payslip"        },
              { href: "/dashboard/employees",        icon: "ti-users",         bg: "rgba(14,124,134,0.12)", color: "var(--info)",    label: "Team Members"      },
              { href: "/dashboard/interview-list",   icon: "ti-user-search",   bg: "rgba(30,78,140,0.12)",  color: "var(--primary)", label: "Interviews"        },
              { href: "/dashboard/my-requests",      icon: "ti-inbox",         bg: "rgba(181,101,29,0.12)", color: "var(--warn)",    label: "My Requests"       },
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
          <div className="card mb-16">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-checks" /> Pending Approvals</div>
              <span className="badge badge-warn">3 items</span>
            </div>
            <div style={{ padding: 0 }}>
              {[
                { name: "Meena Iyer",  type: "Earned Leave · 5 days",       date: "Jul 1–5", icon: "ti-beach",   color: "var(--success)" },
                { name: "Raj Kumar",   type: "Expense Claim · ₹4,800",      date: "Jun 24",  icon: "ti-wallet",  color: "var(--warn)"    },
                { name: "Priya Sharma",type: "Work From Home · 2 days",     date: "Jun 27–28", icon: "ti-home",  color: "var(--info)"    },
              ].map(item => (
                <div key={item.name} style={{ display:"flex",alignItems:"center",gap:12,padding:"14px 20px",borderBottom:"1px solid var(--bg-high)" }}>
                  <div className="qa-icon" style={{ background: "var(--bg-low)", color: item.color, width:36,height:36,fontSize:16,flexShrink:0 }}>
                    <i className={`ti ${item.icon}`} />
                  </div>
                  <div style={{ flex:1 }}>
                    <div style={{ fontSize:13,fontWeight:500,color:"var(--on-bg)" }}>{item.name}</div>
                    <div style={{ fontSize:11,color:"var(--on-variant)" }}>{item.type} · {item.date}</div>
                  </div>
                  <div style={{ display:"flex",gap:6 }}>
                    <button className="btn btn-success btn-sm"><i className="ti ti-check" /></button>
                    <button className="btn btn-ghost btn-sm"><i className="ti ti-x" /></button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-activity" /> Recent Team Activity</div>
            </div>
            <div className="card-body">
              <div className="timeline">
                <div className="tl-item">
                  <div className="tl-dot tl-info"><i className="ti ti-clock" /></div>
                  <div className="tl-body"><div className="tl-title">Raj Kumar clocked in</div><div className="tl-time">Today, 8:58 AM</div></div>
                </div>
                <div className="tl-item">
                  <div className="tl-dot tl-warn"><i className="ti ti-beach" /></div>
                  <div className="tl-body"><div className="tl-title">Meena Iyer applied for leave</div><div className="tl-time">Yesterday, 5:30 PM</div></div>
                </div>
                <div className="tl-item">
                  <div className="tl-dot tl-success"><i className="ti ti-user-check" /></div>
                  <div className="tl-body"><div className="tl-title">Interview completed — Vikram Das</div><div className="tl-time">Jun 21, 3:00 PM</div></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right */}
        <div>
          <BirthdayWidget />
          <div className="card mb-16">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-users" /> Team Attendance Today</div>
              <span className="badge badge-success">10/12 present</span>
            </div>
            <div style={{ padding: 0 }}>
              {[
                { initials:"RK", name:"Raj Kumar",    status:"Present",     time:"9:02 AM",  badge:"badge-success" },
                { initials:"PS", name:"Priya Sharma", status:"Present",     time:"9:15 AM",  badge:"badge-success" },
                { initials:"MI", name:"Meena Iyer",   status:"On Leave",    time:"—",        badge:"badge-warn"    },
                { initials:"AK", name:"Anil Kumar",   status:"Late",        time:"10:30 AM", badge:"badge-error"   },
                { initials:"SS", name:"Sonal Shah",   status:"WFH",         time:"9:05 AM",  badge:"badge-info"    },
              ].map(u => (
                <div key={u.name} style={{ display:"flex",alignItems:"center",gap:12,padding:"11px 20px",borderBottom:"1px solid var(--bg-high)" }}>
                  <div style={{ width:30,height:30,borderRadius:"50%",background:"var(--primary)",color:"#fff",display:"flex",alignItems:"center",justifyContent:"center",fontSize:11,fontWeight:600,flexShrink:0 }}>{u.initials}</div>
                  <div style={{ flex:1 }}>
                    <div style={{ fontSize:13,fontWeight:500 }}>{u.name}</div>
                    <div style={{ fontSize:11,color:"var(--on-variant)" }}>{u.time}</div>
                  </div>
                  <span className={`badge ${u.badge}`}>{u.status}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-calendar" /> Upcoming Leaves</div>
            </div>
            <div style={{ padding: 0 }}>
              {[
                { initials:"MI", name:"Meena Iyer",  dates:"Jul 1–5",  type:"Earned Leave",   status:"Pending your approval" },
                { initials:"RK", name:"Raj Kumar",   dates:"Jul 10",   type:"Sick Leave",     status:"Approved"              },
              ].map(u => (
                <div key={u.name} style={{ display:"flex",alignItems:"center",gap:12,padding:"12px 20px",borderBottom:"1px solid var(--bg-high)" }}>
                  <div style={{ width:32,height:32,borderRadius:"50%",background:"var(--primary)",color:"#fff",display:"flex",alignItems:"center",justifyContent:"center",fontSize:11,fontWeight:600,flexShrink:0 }}>{u.initials}</div>
                  <div style={{ flex:1 }}>
                    <div style={{ fontSize:13,fontWeight:500 }}>{u.name}</div>
                    <div style={{ fontSize:11,color:"var(--on-variant)" }}>{u.dates} · {u.type}</div>
                  </div>
                  <div style={{ fontSize:11,color:"var(--outline)",textAlign:"right" }}>{u.status}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
