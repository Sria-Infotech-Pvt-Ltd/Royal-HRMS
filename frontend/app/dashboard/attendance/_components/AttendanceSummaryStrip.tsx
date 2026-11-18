"use client";

// One slim strip with today's four numbers, in place of four tall cards. Each number is a button that jumps to the matching rows.

import type { StatCards } from "@/types/attendance";
import { PALETTE } from "./attendancePalette";

interface Props {
  cards: StatCards | undefined;
  onJump: (status: string) => void;
}

interface Item { status: string; label: string; value: number | undefined; sub: string; colour: string }

export default function AttendanceSummaryStrip({ cards, onJump }: Props) {
  const total = cards?.total_employees ?? 0;
  const items: Item[] = [
    { status: "present", label: "Present today", value: cards?.present_today, sub: `of ${total} employees`, colour: PALETTE.present },
    { status: "absent", label: "Absent", value: cards?.absent, sub: "No check-in recorded", colour: PALETTE.absent },
    { status: "late", label: "Late arrivals", value: cards?.late_arrivals, sub: "After the grace time", colour: PALETTE.late },
    { status: "on_leave", label: "On leave", value: cards?.on_leave, sub: "Approved leave", colour: PALETTE.on_leave },
  ];
  return (
    <div className="card" role="group" aria-label="Today at a glance" style={{ display: "flex", flexWrap: "wrap", marginBottom: 20 }}>
      {items.map((item, index) => (
        <button
          key={item.status} type="button" onClick={() => onJump(item.status)} title={`Show ${item.label.toLowerCase()}`}
          style={{
            flex: "1 1 180px", display: "flex", alignItems: "center", gap: 14, padding: "14px 20px", textAlign: "left", background: "none", border: 0, cursor: "pointer",
            borderLeft: index === 0 ? "none" : "1px solid var(--outline-v)",
          }}
        >
          <span style={{ fontSize: 28, fontWeight: 800, lineHeight: 1, color: item.colour, fontVariantNumeric: "tabular-nums" }}>{item.value ?? "—"}</span>
          <span>
            <span style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{item.label}</span>
            <span style={{ display: "block", fontSize: 11.5, color: "var(--on-variant)" }}>{item.sub}</span>
          </span>
        </button>
      ))}
    </div>
  );
}
