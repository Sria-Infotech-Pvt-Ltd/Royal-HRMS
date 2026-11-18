import type { CSSProperties } from "react";
import { TeamApprovalStyles } from "./teamApprovalStyles";

interface Props {
  pending:   number;
  leave:     number;
  expense:   number;
  correction: number;
  loading:   boolean;
}

const CARDS = [
  { key: "pending",    label: "Pending Requests",      icon: "ti-clock-hour-4",   bg: "rgba(245,158,11,0.13)", color: "#B45309", hint: "Need a decision" },
  { key: "leave",      label: "Leave Requests",        icon: "ti-beach",          bg: "rgba(34,197,94,0.12)",  color: "#15803D", hint: "Waiting on leave"  },
  { key: "expense",    label: "Expense Requests",      icon: "ti-receipt",        bg: "rgba(245,158,11,0.13)", color: "#B45309", hint: "Waiting on expenses" },
  { key: "correction", label: "Attendance Corrections", icon: "ti-calendar-time", bg: "rgba(59,130,246,0.12)", color: "#1D4ED8", hint: "Waiting on corrections" },
] as const;

export default function SummaryCards({ pending, leave, expense, correction, loading }: Props) {
  const values: Record<string, number> = { pending, leave, expense, correction };

  return (
    <div className="ta-summary-grid">
      <TeamApprovalStyles />
      {CARDS.map(c => (
        <div key={c.key} className="ta-summary-card tv-card" style={{ "--tv-accent": c.color } as CSSProperties}>
          <div className="ta-summary-icon" style={{ background: c.bg, color: c.color }}>
            <i className={`ti ${c.icon}`} />
          </div>
          <div>
            {loading ? (
              <div className="ta-skel" style={{ width: 36, height: 22, marginBottom: 6 }} />
            ) : (
              <div className="ta-summary-value tv-value">{values[c.key]}</div>
            )}
            <div className="ta-summary-label">{c.label}</div>
            {!loading && (
              values[c.key] > 0
                ? <span className="tv-hint">{c.hint}</span>
                : <span className="tv-hint is-clear"><i className="ti ti-check" /> All clear</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
