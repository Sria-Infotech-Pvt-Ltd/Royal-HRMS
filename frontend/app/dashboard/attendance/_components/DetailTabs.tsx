"use client";

// The tab bar of the Attendance Detail panel (Punches, Corrections, History), each with a count.

export interface DetailTab { id: string; label: string; count: number }

interface Props {
  tabs: DetailTab[];
  active: string;
  onChange: (id: string) => void;
}

export default function DetailTabs({ tabs, active, onChange }: Props) {
  return (
    <div role="tablist" aria-label="Attendance detail sections" style={{ display: "flex", gap: 4, borderBottom: "1px solid var(--outline-v)", marginBottom: 16 }}>
      {tabs.map(tab => {
        const selected = tab.id === active;
        return (
          <button
            key={tab.id} type="button" role="tab" aria-selected={selected} onClick={() => onChange(tab.id)}
            style={{ display: "flex", alignItems: "center", gap: 7, padding: "10px 14px", background: "none", border: 0, cursor: "pointer", fontSize: 13, fontWeight: selected ? 700 : 500, color: selected ? "var(--primary)" : "var(--on-variant)", borderBottom: `2px solid ${selected ? "var(--primary)" : "transparent"}`, marginBottom: -1 }}
          >
            {tab.label}
            <span style={{ fontSize: 11.5, fontWeight: 700, padding: "1px 8px", borderRadius: 999, background: selected ? "var(--primary)" : "var(--bg-low)", color: selected ? "#fff" : "var(--on-variant)", fontVariantNumeric: "tabular-nums" }}>{tab.count}</span>
          </button>
        );
      })}
    </div>
  );
}
