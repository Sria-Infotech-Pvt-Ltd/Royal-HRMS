"use client";

import { EMP_DATA, fmt, grossEarnings, netSalary } from "./payrollData";

interface Props { onRunPayroll: () => void; }

const STATS = [
  { label: "Total Employees",   value: "248",         sub: "Active this month",     icon: "ti-users",         cls: "si-primary"  },
  { label: "Gross Payroll",     value: "₹34,55,000",  sub: "Before deductions",     icon: "ti-cash",          cls: "si-info"     },
  { label: "Net Payroll",       value: "₹30,30,830",  sub: "After all deductions",  icon: "ti-credit-card",   cls: "si-success"  },
  { label: "Pending Payroll",   value: "3",           sub: "Awaiting approval",     icon: "ti-clock",         cls: "si-warn"     },
  { label: "Processed Payroll", value: "12",          sub: "Disbursed this quarter", icon: "ti-circle-check",  cls: "si-success"  },
];

const RECENT_RUNS = [
  { month: "May 2026",   employees: 246, gross: "₹33,90,500", net: "₹29,84,200", date: "30 May 2026",  status: "paid"       },
  { month: "Apr 2026",   employees: 244, gross: "₹33,10,000", net: "₹29,12,800", date: "30 Apr 2026",  status: "paid"       },
  { month: "Mar 2026",   employees: 243, gross: "₹32,50,000", net: "₹28,60,500", date: "31 Mar 2026",  status: "paid"       },
  { month: "Jun 2026",   employees: 248, gross: "₹34,55,000", net: "₹30,30,830", date: "Pending",      status: "pending"    },
];

const STATUS_BADGE: Record<string, string> = {
  paid:       "badge badge-success",
  pending:    "badge badge-warn",
  processing: "badge badge-info",
  failed:     "badge badge-error",
};

const CAL_DAYS = ["S","M","T","W","T","F","S"];
const CAL_DATES = Array.from({ length: 30 }, (_, i) => i + 1);
const PAY_DATE = 30;
const HOLIDAYS = [8, 15, 21];

export default function PayrollDashboard({ onRunPayroll }: Props) {
  const totalGross = EMP_DATA.reduce((a, e) => a + grossEarnings(e), 0);
  const totalNet   = EMP_DATA.reduce((a, e) => a + netSalary(e),     0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* Stats row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 16 }}>
        {STATS.map(s => (
          <div key={s.label} className="stat-card">
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 8 }}>
              <div>
                <div className="stat-label">{s.label}</div>
                <div className="stat-value" style={{ fontSize: 22 }}>{s.value}</div>
                <div className="stat-sub">{s.sub}</div>
              </div>
              <div className={`stat-icon ${s.cls}`} style={{ float: "none", margin: 0 }}>
                <i className={`ti ${s.icon}`} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Calendar + Recent runs */}
      <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 16 }}>

        {/* Payroll Calendar */}
        <div className="card">
          <div className="card-header">
            <div className="card-title"><i className="ti ti-calendar-event" /> Payroll Calendar</div>
            <span className="badge badge-primary">June 2026</span>
          </div>
          <div className="card-body" style={{ padding: 16 }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 2, marginBottom: 8 }}>
              {CAL_DAYS.map((d, i) => (
                <div key={i} style={{ textAlign: "center", fontSize: 10, fontWeight: 600, color: "var(--on-variant)", padding: "4px 0" }}>{d}</div>
              ))}
              {/* 6 empty cells for June starting on Monday (index 1) */}
              <div />
              {CAL_DATES.map(d => {
                const isPayDay  = d === PAY_DATE;
                const isHoliday = HOLIDAYS.includes(d);
                const isToday   = d === 30;
                return (
                  <div
                    key={d}
                    style={{
                      textAlign: "center", fontSize: 12, padding: "5px 2px",
                      borderRadius: 6, fontWeight: isToday ? 700 : 400,
                      background: isPayDay ? "var(--primary)" : isHoliday ? "var(--warn-c)" : "transparent",
                      color: isPayDay ? "#fff" : isHoliday ? "var(--warn)" : "var(--on-bg)",
                      border: isToday && !isPayDay ? "1.5px solid var(--primary)" : "none",
                    }}
                  >
                    {d}
                  </div>
                );
              })}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 12, borderTop: "1px solid var(--outline-v)", paddingTop: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
                <div style={{ width: 12, height: 12, borderRadius: 3, background: "var(--primary)" }} />
                <span>Salary Date — 30 Jun</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
                <div style={{ width: 12, height: 12, borderRadius: 3, background: "var(--warn-c)", border: "1px solid var(--warn)" }} />
                <span>Holidays (3)</span>
              </div>
            </div>
            <button className="btn btn-filled btn-sm" style={{ width: "100%", marginTop: 14, justifyContent: "center" }} onClick={onRunPayroll}>
              <i className="ti ti-player-play" /> Run June Payroll
            </button>
          </div>
        </div>

        {/* Recent Payroll Runs */}
        <div className="card">
          <div className="card-header">
            <div className="card-title"><i className="ti ti-history" /> Recent Payroll Runs</div>
            <button className="btn btn-ghost btn-sm"><i className="ti ti-download" /> Export</button>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Month</th>
                  <th>Employees</th>
                  <th>Gross Payroll</th>
                  <th>Net Payroll</th>
                  <th>Salary Date</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {RECENT_RUNS.map(r => (
                  <tr key={r.month}>
                    <td style={{ fontWeight: 600 }}>{r.month}</td>
                    <td>{r.employees}</td>
                    <td>{r.gross}</td>
                    <td style={{ fontWeight: 600, color: "var(--success)" }}>{r.net}</td>
                    <td>{r.date}</td>
                    <td><span className={STATUS_BADGE[r.status]}>{r.status.charAt(0).toUpperCase() + r.status.slice(1)}</span></td>
                    <td>
                      <button className="btn btn-ghost btn-sm">
                        <i className="ti ti-eye" /> View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Sample employee payroll summary */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-users" /> Employee Payroll Preview — June 2026</div>
          <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Showing 5 of 248 employees</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Employee</th>
                <th>Department</th>
                <th>Basic</th>
                <th>HRA</th>
                <th>Gross Earnings</th>
                <th>Deductions</th>
                <th>Net Salary</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {EMP_DATA.map(e => {
                const gross = grossEarnings(e);
                const net   = netSalary(e);
                const ded   = gross - net + (e.travel + e.fuel + e.medical + e.internet + e.food);
                return (
                  <tr key={e.id}>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <div style={{ width: 30, height: 30, borderRadius: "50%", background: "var(--primary)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, flexShrink: 0 }}>{e.avatar}</div>
                        <div>
                          <div style={{ fontWeight: 600 }}>{e.name}</div>
                          <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{e.id}</div>
                        </div>
                      </div>
                    </td>
                    <td>{e.dept}</td>
                    <td>{fmt(e.basic)}</td>
                    <td>{fmt(e.hra)}</td>
                    <td style={{ fontWeight: 600 }}>{fmt(gross)}</td>
                    <td style={{ color: "var(--error)" }}>{fmt(e.pf + e.esi + e.pt + e.tds + e.loan_emi + e.advance + e.lop)}</td>
                    <td style={{ fontWeight: 700, color: "var(--success)" }}>{fmt(net)}</td>
                    <td><span className="badge badge-warn">Pending</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
