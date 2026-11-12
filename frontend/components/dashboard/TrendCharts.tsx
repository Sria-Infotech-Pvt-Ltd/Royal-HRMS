"use client";

// Historical (month-over-month) analytics widgets — Stage 2 of the
// System Admin dashboard analytics work. Each card fetches its own
// trailing-6-month series and renders a simple bar chart, same visual
// language as DeptHeadcountChart.tsx (plain divs, no chart library).

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";

interface HeadcountPoint { label: string; count: number }
interface LeavePoint { label: string; approved: number; rejected: number }
interface PayrollCostPoint { label: string; amount: number }

function LoadingRow() {
  return (
    <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
      <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
    </div>
  );
}

function EmptyRow({ icon, text }: { icon: string; text: string }) {
  return (
    <div style={{ padding: "24px 20px", textAlign: "center", fontSize: 13, color: "var(--on-variant)" }}>
      <i className={`ti ${icon}`} style={{ fontSize: 22, display: "block", marginBottom: 6, opacity: 0.3 }} />
      {text}
    </div>
  );
}

export function HeadcountTrendCard() {
  const { data, loading } = useFetch<{ series: HeadcountPoint[] }>(API.dashboard.headcountTrend);
  const series = data?.series ?? [];
  const max = Math.max(1, ...series.map(s => s.count));

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-trending-up" /> Headcount Growth (6 months)</div>
      </div>
      {loading ? <LoadingRow /> : series.length === 0 ? (
        <EmptyRow icon="ti-trending-up" text="No data available" />
      ) : (
        <div style={{ padding: "16px 20px", display: "flex", alignItems: "flex-end", gap: 10, height: 140 }}>
          {series.map(point => (
            <div key={point.label} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 6, height: "100%", justifyContent: "flex-end" }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: "var(--on-bg)" }}>{point.count}</span>
              <div
                title={`${point.label}: ${point.count}`}
                style={{
                  width: "100%", maxWidth: 32,
                  height: `${Math.max(4, (point.count / max) * 100)}px`,
                  background: "var(--primary)", borderRadius: "4px 4px 0 0",
                }}
              />
              <span style={{ fontSize: 10, color: "var(--on-variant)" }}>{point.label.split(" ")[0]}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function LeaveTrendCard() {
  const { data, loading } = useFetch<{ series: LeavePoint[] }>(API.dashboard.leaveTrend);
  const series = data?.series ?? [];
  const max = Math.max(1, ...series.map(s => Math.max(s.approved, s.rejected)));
  const hasAny = series.some(s => s.approved > 0 || s.rejected > 0);

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-calendar-stats" /> Leave Approvals vs Rejections (6 months)</div>
        <div style={{ display: "flex", gap: 10, fontSize: 11, color: "var(--on-variant)" }}>
          <span><span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: "var(--success)", marginRight: 4 }} />Approved</span>
          <span><span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: "var(--error)", marginRight: 4 }} />Rejected</span>
        </div>
      </div>
      {loading ? <LoadingRow /> : !hasAny ? (
        <EmptyRow icon="ti-calendar-stats" text="No leave requests recorded in this period" />
      ) : (
        <div style={{ padding: "16px 20px", display: "flex", alignItems: "flex-end", gap: 10, height: 140 }}>
          {series.map(point => (
            <div key={point.label} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 6, height: "100%", justifyContent: "flex-end" }}>
              <div style={{ display: "flex", gap: 3, alignItems: "flex-end", height: "100%" }}>
                <div title={`${point.label}: ${point.approved} approved`} style={{ width: 12, height: `${Math.max(4, (point.approved / max) * 100)}px`, background: "var(--success)", borderRadius: "3px 3px 0 0" }} />
                <div title={`${point.label}: ${point.rejected} rejected`} style={{ width: 12, height: `${Math.max(4, (point.rejected / max) * 100)}px`, background: "var(--error)", borderRadius: "3px 3px 0 0" }} />
              </div>
              <span style={{ fontSize: 10, color: "var(--on-variant)" }}>{point.label.split(" ")[0]}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function formatInr(amount: number): string {
  if (amount >= 100000) return `₹${(amount / 100000).toFixed(1)}L`;
  if (amount >= 1000) return `₹${(amount / 1000).toFixed(0)}K`;
  return `₹${amount}`;
}

export function PayrollCostTrendCard() {
  const { data, loading } = useFetch<{ series: PayrollCostPoint[] }>(API.dashboard.payrollCostTrend);
  const series = data?.series ?? [];
  const max = Math.max(1, ...series.map(s => s.amount));

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-report-money" /> Payroll Cost (last {series.length || 6} cycles)</div>
      </div>
      {loading ? <LoadingRow /> : series.length === 0 ? (
        <EmptyRow icon="ti-report-money" text="No completed payroll cycles yet" />
      ) : (
        <div style={{ padding: "16px 20px", display: "flex", alignItems: "flex-end", gap: 10, height: 140 }}>
          {series.map(point => (
            <div key={point.label} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 6, height: "100%", justifyContent: "flex-end" }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: "var(--on-bg)" }}>{formatInr(point.amount)}</span>
              <div
                title={`${point.label}: ${formatInr(point.amount)}`}
                style={{
                  width: "100%", maxWidth: 32,
                  height: `${Math.max(4, (point.amount / max) * 100)}px`,
                  background: "var(--warn)", borderRadius: "4px 4px 0 0",
                }}
              />
              <span style={{ fontSize: 10, color: "var(--on-variant)" }}>{point.label.split(" ")[0]}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
