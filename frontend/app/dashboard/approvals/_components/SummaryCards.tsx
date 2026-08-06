interface Props {
  pending:   number;
  leave:     number;
  expense:   number;
  correction: number;
  loading:   boolean;
}

const CARDS = [
  { key: "pending",    label: "Pending Requests",      icon: "ti-clock-hour-4",   bg: "rgba(245,158,11,0.13)", color: "#B45309" },
  { key: "leave",      label: "Leave Requests",        icon: "ti-beach",          bg: "rgba(34,197,94,0.12)",  color: "#15803D" },
  { key: "expense",    label: "Expense Requests",      icon: "ti-receipt",        bg: "rgba(245,158,11,0.13)", color: "#B45309" },
  { key: "correction", label: "Attendance Corrections", icon: "ti-calendar-time", bg: "rgba(59,130,246,0.12)", color: "#1D4ED8" },
] as const;

export default function SummaryCards({ pending, leave, expense, correction, loading }: Props) {
  const values: Record<string, number> = { pending, leave, expense, correction };

  return (
    <div className="ta-summary-grid">
      {CARDS.map(c => (
        <div key={c.key} className="ta-summary-card">
          <div className="ta-summary-icon" style={{ background: c.bg, color: c.color }}>
            <i className={`ti ${c.icon}`} />
          </div>
          <div>
            {loading ? (
              <div className="ta-skel" style={{ width: 36, height: 22, marginBottom: 6 }} />
            ) : (
              <div className="ta-summary-value">{values[c.key]}</div>
            )}
            <div className="ta-summary-label">{c.label}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
