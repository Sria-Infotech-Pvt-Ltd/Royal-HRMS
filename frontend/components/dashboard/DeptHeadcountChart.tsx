"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { DeptHeadcount } from "@/types/dashboard";

interface Props { endpoint?: string }

const BAR_COLORS = [
  "var(--primary)",
  "var(--success)",
  "var(--info)",
  "var(--warn)",
  "var(--secondary)",
  "var(--error)",
];

export default function DeptHeadcountChart({ endpoint = API.dashboard.departmentHeadcount }: Props) {
  const { data, loading } = useFetch<DeptHeadcount[]>(endpoint);

  const rows = Array.isArray(data) ? data : [];
  const maxCount = rows.length > 0 ? Math.max(...rows.map(r => r.count)) : 1;
  const total = rows.reduce((sum, r) => sum + r.count, 0);

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-chart-bar" /> Department Headcount</div>
        {!loading && total > 0 && (
          <span className="badge badge-primary">{total} total</span>
        )}
      </div>

      {loading ? (
        <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
        </div>
      ) : rows.length === 0 ? (
        <div style={{ padding: "24px 20px", textAlign: "center", fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-chart-bar" style={{ fontSize: 22, display: "block", marginBottom: 6, opacity: 0.3 }} />
          No data available
        </div>
      ) : (
        <div style={{ padding: "12px 20px 16px" }}>
          {rows.map((row, index) => {
            const pct = maxCount > 0 ? (row.count / maxCount) * 100 : 0;
            const color = BAR_COLORS[index % BAR_COLORS.length];
            return (
              <div key={row.department} style={{ marginBottom: 12 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                    <span style={{ width: 9, height: 9, borderRadius: 2, background: color, flexShrink: 0 }} />
                    <span style={{ fontSize: 12, color: "var(--on-bg)", fontWeight: 500 }}>{row.department}</span>
                  </div>
                  <span style={{ fontSize: 12, fontWeight: 700, color: "var(--on-bg)" }}>{row.count}</span>
                </div>
                <div style={{ height: 7, borderRadius: 4, background: "var(--bg-high)", overflow: "hidden" }}>
                  <div style={{
                    height: "100%",
                    width: `${pct}%`,
                    background: color,
                    borderRadius: 4,
                    transition: "width 0.4s ease",
                  }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
