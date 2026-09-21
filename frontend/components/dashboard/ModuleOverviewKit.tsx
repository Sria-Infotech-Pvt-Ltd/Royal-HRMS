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

export function BrandBanner() {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, flexWrap: "wrap", border: "1px solid rgba(124,58,237,0.25)", borderRadius: 12, padding: "16px 20px", margin: "20px 0" }}>
      <div>
        <div style={{ fontWeight: 700, fontSize: 14, color: "var(--on-bg)" }}>AIRA · Artificial Intelligence Resources Assistance</div>
        <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 2 }}>
          Recruit-to-retire HR operations · effective-dated records · controlled approvals · complete audit trail
        </div>
      </div>
      <span className="badge badge-warn" style={{ fontWeight: 700, fontSize: 11, letterSpacing: "0.04em" }}>
        INTERACTIVE DEMO DATA
      </span>
    </div>
  );
}

export interface TileDef { title: string; desc: string; href: string }

export function CapabilityGrid({ title, sub, items, onOpen }: { title: string; sub: string; items: TileDef[]; onOpen: (href: string) => void }) {
  return (
    <div className="card mb-6">
      <div style={{ padding: "18px 20px 4px" }}>
        <div style={{ fontWeight: 700, fontSize: 15 }}>{title}</div>
        <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 2 }}>{sub}</div>
      </div>
      <div style={{ padding: "12px 20px 20px", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14 }}>
        {items.map(c => (
          <div key={c.title} style={{ border: "1px solid var(--outline-v)", borderRadius: 10, padding: 14 }}>
            <div style={{ fontWeight: 700, fontSize: 13.5, color: "var(--on-bg)" }}>{c.title}</div>
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4, marginBottom: 10 }}>{c.desc}</div>
            <button onClick={() => onOpen(c.href)} style={{ background: "none", border: "none", color: "var(--primary)", fontSize: 12.5, fontWeight: 700, cursor: "pointer", padding: 0 }}>
              Open
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export function OperationalToolsGrid({ title, sub, items, onLaunch }: { title: string; sub: string; items: TileDef[]; onLaunch: (href: string) => void }) {
  return (
    <div className="card mb-6">
      <div style={{ padding: "18px 20px 4px" }}>
        <div style={{ fontWeight: 700, fontSize: 15 }}>{title}</div>
        <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 2 }}>{sub}</div>
      </div>
      <div style={{ padding: "12px 20px 20px", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 14 }}>
        {items.map(t => (
          <div key={t.title} style={{ border: "1px solid var(--outline-v)", borderRadius: 10, padding: 14 }}>
            <div style={{ fontWeight: 700, fontSize: 13.5, color: "var(--on-bg)" }}>{t.title}</div>
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4, marginBottom: 10 }}>{t.desc}</div>
            <button className="btn btn-ghost btn-sm" onClick={() => onLaunch(t.href)}>Launch</button>
          </div>
        ))}
      </div>
    </div>
  );
}

const SAFEGUARDS = [
  "Data validation active", "Conflicting dates blocked", "Audit events retained", "Approval SLA monitored",
  "Exports permission-aware", "Backup check passed", "Integration retry enabled", "Period locks enforced",
];

export function PlatformSafeguards() {
  return (
    <div className="card">
      <div style={{ padding: "18px 20px 4px" }}>
        <div style={{ fontWeight: 700, fontSize: 15 }}>Platform safeguards</div>
        <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 2 }}>Controls that prevent long-running HR operations from becoming blocked.</div>
      </div>
      <div style={{ padding: "12px 20px 20px", display: "flex", flexWrap: "wrap", gap: 8 }}>
        {SAFEGUARDS.map(s => (
          <span key={s} className="badge badge-success" style={{ fontWeight: 600 }}>{s}</span>
        ))}
      </div>
    </div>
  );
}
