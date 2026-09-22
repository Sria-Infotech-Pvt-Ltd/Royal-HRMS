"use client";

// Shared building blocks for every module's "overview landing" page
// (Dashboard, Organization, and now Attendance/Leave/Payroll/Performance/
// Reports/Settings) — extracted from the original HRDashboard.tsx so the
// same KPI tile / overview row / quick-action tile / brand banner /
// capability grid / operational-tools grid / safeguards-pills pattern isn't
// re-implemented from scratch per module. Every module's real numbers come
// from its own real backend endpoint — this file only renders whatever
// data it's given, never invents any of it.

export function KpiTile({ label, value, sub, tone = "brand" }: {
  label: string; value: string | number; sub: string; tone?: "brand" | "ok" | "warn" | "crit";
}) {
  return (
    <div className="stat">
      <div className="top">
        <div className="lbl">{label}</div>
        <div className={`ico ${tone}`}>
          <div style={{ width: 8, height: 8, background: "currentColor", transform: "rotate(45deg)", borderRadius: 2 }} />
        </div>
      </div>
      <div className="num">{value}</div>
      <div className="sub">{sub}</div>
    </div>
  );
}

export function OverviewRow({ label, sub, chip, chipTone, onOpen }: {
  label: string; sub: string; chip: string; chipTone: "warn" | "error" | "success"; onOpen: () => void;
}) {
  const stateClass = chipTone === "warn" ? "warn" : chipTone === "error" ? "crit" : "ok";
  return (
    <div className="module-row">
      <div className="mr-label">{label}</div>
      <div className="mr-meta">{sub}</div>
      <span className={`state ${stateClass}`}>{chip}</span>
      <button onClick={onOpen} className="mr-open">Open</button>
    </div>
  );
}

export function QuickActionTile({ title, sub, onClick }: { title: string; sub: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className="quick">
      <div className="q-title">{title}</div>
      <div className="q-sub">{sub}</div>
    </button>
  );
}

export function WeeklyBarChart({ data }: { data: { label: string; count: number }[] }) {
  const maxCount = Math.max(1, ...data.map(d => d.count));
  return (
    <div className="chart-bars">
      {data.map((d, i) => (
        <i key={i} style={{ height: `${Math.max(12, (d.count / maxCount) * 100)}%` }}>{d.label}</i>
      ))}
    </div>
  );
}

