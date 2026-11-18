"use client";

// The status filter and the search box in one row, sitting on top of the attendance table. Replaces the separate row of count chips.

import type { SummaryChips } from "@/types/attendance";
import { STATUS_TABS, tabCount } from "./attendanceView";

interface Props {
  status: string;
  onStatusChange: (status: string) => void;
  chips: SummaryChips | undefined;
  search: string;
  onSearchChange: (value: string) => void;
}

export default function AttendanceStatusTabs({ status, onStatusChange, chips, search, onSearchChange }: Props) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", padding: "0 16px", borderBottom: "1px solid var(--outline-v)" }}>
      <div role="group" aria-label="Filter by status" style={{ display: "flex", gap: 2, flexWrap: "wrap", flex: 1 }}>
        {STATUS_TABS.map(tab => {
          const selected = status === tab.key;
          const count = tabCount(tab.key, chips);
          return (
            <button
              key={tab.key || "all"} type="button" aria-pressed={selected} onClick={() => onStatusChange(selected && tab.key !== "" ? "" : tab.key)}
              style={{
                display: "flex", alignItems: "center", gap: 7, padding: "13px 12px", background: "none", border: 0, cursor: "pointer", fontSize: 13,
                fontWeight: selected ? 700 : 500, color: selected ? "var(--on-bg)" : "var(--on-variant)",
                borderBottom: `2px solid ${selected ? tab.colour : "transparent"}`, marginBottom: -1,
              }}
            >
              {tab.key !== "" && <span aria-hidden="true" style={{ width: 7, height: 7, borderRadius: "50%", background: tab.colour }} />}
              {tab.label}
              {count !== null && (
                <span style={{ fontSize: 11.5, fontWeight: 700, padding: "1px 7px", borderRadius: 999, fontVariantNumeric: "tabular-nums", background: selected ? "var(--bg-low)" : "transparent", color: count > 0 ? "var(--on-bg)" : "var(--outline)" }}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>
      <div style={{ position: "relative", margin: "8px 0" }}>
        <i className="ti ti-search" aria-hidden="true" style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--outline)", fontSize: 14 }} />
        <input
          type="search" aria-label="Search employees" className="field-input" placeholder="Search name or ID" value={search}
          onChange={event => onSearchChange(event.target.value)} style={{ width: 220, paddingLeft: 30 }}
        />
      </div>
    </div>
  );
}
