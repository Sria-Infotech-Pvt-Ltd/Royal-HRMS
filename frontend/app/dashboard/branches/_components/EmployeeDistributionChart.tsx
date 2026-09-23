"use client";

import type { BranchDistribution } from "./_data";

export default function EmployeeDistributionChart({ distribution }: { distribution: BranchDistribution[] }) {
  if (distribution.length === 0) return null;

  const maxEmp = Math.max(...distribution.map(d => d.employees), 8);
  const colors = ["var(--primary)", "var(--info)", "var(--secondary)", "var(--warn)"];

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <i className="ti ti-chart-bar" /> Employee Distribution by Company Code
        </div>
      </div>
      <div className="card-body">
        <div style={{ position: "relative", height: "260px", paddingLeft: "40px", paddingBottom: "40px", paddingTop: "20px" }}>
          {/* Y-axis grid lines */}
          <div style={{ position: "absolute", inset: "20px 0 40px 40px", display: "flex", flexDirection: "column-reverse", justifyContent: "space-between" }}>
            {[0, 2, 4, 6, 8].map(val => (
              <div key={val} style={{ borderBottom: val === 0 ? "1px solid var(--outline)" : "1px dashed var(--outline-v)", position: "relative", width: "100%" }}>
                <span style={{ position: "absolute", left: "-24px", top: "-8px", fontSize: "11px", color: "var(--on-variant)" }}>{val}</span>
              </div>
            ))}
          </div>

          {/* Bars */}
          <div style={{ position: "absolute", inset: "20px 0 40px 40px", display: "flex", alignItems: "flex-end", justifyContent: "space-around" }}>
            {distribution.map((dist, i) => {
              const heightPct = (dist.employees / maxEmp) * 100;
              return (
                <div key={dist.branch_code} style={{ display: "flex", flexDirection: "column", alignItems: "center", height: "100%", justifyContent: "flex-end", zIndex: 1, position: "relative" }}>
                  <div style={{
                    width: "36px",
                    height: `${heightPct}%`,
                    background: colors[i % colors.length],
                    borderRadius: "6px 6px 0 0",
                    transition: "height 0.3s ease",
                    cursor: "pointer"
                  }} title={`${dist.branch}: ${dist.employees} Employees`} />
                  <div style={{ position: "absolute", bottom: "-30px", fontSize: "12px", color: "var(--on-variant)", whiteSpace: "nowrap", textAlign: "center" }}>
                    {dist.branch}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
