"use client";

const MONTHLY_TREND = [
  { month: "Jan", gross: 2950000, net: 2620000 },
  { month: "Feb", gross: 2980000, net: 2648000 },
  { month: "Mar", gross: 3050000, net: 2718000 },
  { month: "Apr", gross: 3100000, net: 2756000 },
  { month: "May", gross: 3180000, net: 2822000 },
  { month: "Jun", gross: 3455000, net: 3030830 },
];

const DEPT_BREAKDOWN = [
  { dept: "Engineering", gross: 80500,  net: 70085, headcount: 28 },
  { dept: "Sales",       gross: 94000,  net: 89800, headcount: 35 },
  { dept: "Finance",     gross: 65000,  net: 52720, headcount: 18 },
  { dept: "HR",          gross: 56500,  net: 49188, headcount: 12 },
  { dept: "Operations",  gross: 49500,  net: 41290, headcount: 42 },
];

const OT_MONTHS = [
  { month: "Jan", cost: 42000 },
  { month: "Feb", cost: 38000 },
  { month: "Mar", cost: 51000 },
  { month: "Apr", cost: 47000 },
  { month: "May", cost: 63000 },
  { month: "Jun", cost: 65000 },
];

function fmt(n: number) { return "₹" + (n / 100000).toFixed(1) + "L"; }
function fmtK(n: number) { return "₹" + (n / 1000).toFixed(0) + "K"; }

function BarChart({ data, valueKey, labelKey, color, maxOverride }: {
  data: Record<string, number | string>[];
  valueKey: string;
  labelKey: string;
  color: string;
  maxOverride?: number;
}) {
  const max = maxOverride ?? Math.max(...data.map(d => d[valueKey] as number));
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 120, padding: "0 4px" }}>
      {data.map((d, i) => {
        const pct = ((d[valueKey] as number) / max) * 100;
        return (
          <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: 1, gap: 4 }}>
            <div style={{ fontSize: 10, color: "var(--on-variant)", fontWeight: 600 }}>{fmtK(d[valueKey] as number)}</div>
            <div style={{ width: "100%", background: color, borderRadius: "3px 3px 0 0", height: `${pct}%`, minHeight: 4, transition: "height 0.3s" }} />
            <div style={{ fontSize: 10, color: "var(--on-variant)" }}>{d[labelKey]}</div>
          </div>
        );
      })}
    </div>
  );
}

function TrendChart() {
  const max = Math.max(...MONTHLY_TREND.map(d => d.gross));
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 130, padding: "0 4px" }}>
      {MONTHLY_TREND.map((d, i) => {
        const grossPct = (d.gross / max) * 100;
        const netPct   = (d.net   / max) * 100;
        return (
          <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: 1, gap: 4 }}>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 110, width: "100%" }}>
              <div style={{ flex: 1, background: "var(--primary)", borderRadius: "3px 3px 0 0", height: `${grossPct}%`, minHeight: 4 }} />
              <div style={{ flex: 1, background: "var(--success)", borderRadius: "3px 3px 0 0", height: `${netPct}%`, minHeight: 4 }} />
            </div>
            <div style={{ fontSize: 10, color: "var(--on-variant)" }}>{d.month}</div>
          </div>
        );
      })}
    </div>
  );
}

function DonutSegment({ pct, color, offset }: { pct: number; color: string; offset: number }) {
  const r  = 44;
  const c  = 2 * Math.PI * r;
  const dash = (pct / 100) * c;
  return (
    <circle
      r={r} cx={50} cy={50} fill="none" stroke={color} strokeWidth={12}
      strokeDasharray={`${dash} ${c - dash}`}
      strokeDashoffset={-offset * c / 100}
      style={{ transition: "stroke-dasharray 0.5s" }}
    />
  );
}

const DEPT_COLORS = ["var(--primary)", "var(--info)", "var(--success)", "var(--warn)", "var(--purple)"];

export default function PayrollAnalytics() {
  const deptTotal = DEPT_BREAKDOWN.reduce((s, d) => s + d.gross, 0);
  const deptPcts  = DEPT_BREAKDOWN.map(d => Math.round((d.gross / deptTotal) * 100));
  let offset = 0;
  const segments: { pct: number; color: string; offset: number }[] = deptPcts.map((pct, i) => {
    const seg = { pct, color: DEPT_COLORS[i], offset };
    offset += pct;
    return seg;
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* KPI row */}
      <div className="stats-grid">
        {[
          { label: "Avg. Salary",    value: "₹69,083",  sub: "Per employee / month", icon: "ti-user", cls: "si-primary" },
          { label: "Payroll Growth", value: "+8.7%",    sub: "vs last quarter",       icon: "ti-trending-up", cls: "si-success" },
          { label: "OT Cost",        value: "₹65,000",  sub: "June 2026",             icon: "ti-clock", cls: "si-warn"    },
          { label: "Compliance",     value: "100%",     sub: "Statutory deductions",  icon: "ti-shield-check", cls: "si-info" },
        ].map(s => (
          <div key={s.label} className="stat-card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
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

      {/* Monthly trend + Dept donut */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 16 }}>
        <div className="card">
          <div className="card-header">
            <div className="card-title"><i className="ti ti-chart-line" /> Monthly Payroll Trend</div>
            <div style={{ display: "flex", gap: 12, fontSize: 11 }}>
              <span style={{ display: "flex", alignItems: "center", gap: 4 }}><span style={{ width: 10, height: 10, borderRadius: 2, background: "var(--primary)", display: "inline-block" }} /> Gross</span>
              <span style={{ display: "flex", alignItems: "center", gap: 4 }}><span style={{ width: 10, height: 10, borderRadius: 2, background: "var(--success)", display: "inline-block" }} /> Net</span>
            </div>
          </div>
          <div className="card-body">
            <TrendChart />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 8, marginTop: 12 }}>
              {MONTHLY_TREND.map(d => (
                <div key={d.month} style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: "var(--primary)" }}>{fmt(d.gross)}</div>
                  <div style={{ fontSize: 10, color: "var(--success)" }}>{fmt(d.net)}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title"><i className="ti ti-chart-donut" /> Cost by Department</div>
          </div>
          <div className="card-body" style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <svg viewBox="0 0 100 100" style={{ width: 130, height: 130, transform: "rotate(-90deg)" }}>
              {segments.map((seg, i) => <DonutSegment key={i} {...seg} />)}
            </svg>
            <div style={{ width: "100%", marginTop: 12 }}>
              {DEPT_BREAKDOWN.map((d, i) => (
                <div key={d.dept} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, fontSize: 12 }}>
                  <div style={{ width: 10, height: 10, borderRadius: 2, background: DEPT_COLORS[i], flexShrink: 0 }} />
                  <span style={{ flex: 1 }}>{d.dept}</span>
                  <span style={{ fontWeight: 600 }}>{deptPcts[i]}%</span>
                  <span style={{ color: "var(--on-variant)" }}>({d.headcount} emp)</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* OT cost + Earnings vs Deductions */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="card">
          <div className="card-header">
            <div className="card-title"><i className="ti ti-clock" /> Overtime Cost Trend</div>
          </div>
          <div className="card-body">
            <BarChart data={OT_MONTHS as Record<string, number | string>[]} valueKey="cost" labelKey="month" color="var(--warn)" />
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title"><i className="ti ti-chart-bar" /> Earnings vs Deductions</div>
          </div>
          <div className="card-body">
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {DEPT_BREAKDOWN.map((d, i) => {
                const dedPct = Math.round(((d.gross - d.net) / d.gross) * 100);
                return (
                  <div key={d.dept}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 12 }}>
                      <span style={{ fontWeight: 500 }}>{d.dept}</span>
                      <span style={{ color: "var(--on-variant)" }}>{dedPct}% deductions</span>
                    </div>
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width: `${100 - dedPct}%`, background: DEPT_COLORS[i] }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
