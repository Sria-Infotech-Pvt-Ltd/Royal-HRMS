"use client";

// The colour legend of the month, doubling as a filter: every status is always shown in its colour with how many days had it, and
// clicking one highlights just those days. A status with no days this month is dimmed and cannot be chosen.

import { FILTER_STATUSES, STATUS_META } from "./monthView";

interface Props {
  counts: Record<string, number>;
  active: string;
  onChange: (status: string) => void;
}

export default function MonthStatusFilter({ counts, active, onChange }: Props) {
  return (
    <div role="group" aria-label="Highlight days by status" style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
      {FILTER_STATUSES.map(status => {
        const meta = STATUS_META[status];
        const count = counts[status] ?? 0;
        const selected = active === status;
        return (
          <button
            key={status} type="button" aria-pressed={selected} disabled={count === 0 && !selected} onClick={() => onChange(selected ? "" : status)}
            style={{
              display: "flex", alignItems: "center", gap: 7, padding: "5px 12px", borderRadius: 999, cursor: count === 0 ? "default" : "pointer", fontSize: 12.5,
              background: selected ? meta.colour : meta.bg, border: `1px solid ${meta.colour}`, color: selected ? "#fff" : "var(--on-bg)",
              fontWeight: selected ? 700 : 600, opacity: count === 0 && !selected ? 0.45 : 1,
            }}
          >
            <span aria-hidden="true" style={{ width: 9, height: 9, borderRadius: "50%", background: selected ? "#fff" : meta.colour }} />
            {meta.label}
            <span style={{ fontWeight: 800, fontVariantNumeric: "tabular-nums", color: selected ? "#fff" : meta.colour }}>{count}</span>
          </button>
        );
      })}
      {active && <button type="button" className="btn btn-ghost btn-sm" onClick={() => onChange("")}>Clear</button>}
    </div>
  );
}
