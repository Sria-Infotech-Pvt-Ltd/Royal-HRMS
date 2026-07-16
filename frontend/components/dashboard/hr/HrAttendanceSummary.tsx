"use client";

import { useEffect } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { AttendanceSummary } from "@/types/dashboard";

const CHIPS: { key: keyof AttendanceSummary; label: string; color: string; bg: string }[] = [
  { key: "present",    label: "Present",    color: "#16a34a", bg: "rgba(22,163,74,0.12)"   },
  { key: "late",       label: "Late",       color: "#d97706", bg: "rgba(217,119,6,0.12)"   },
  { key: "absent",     label: "Absent",     color: "#dc2626", bg: "rgba(220,38,38,0.12)"   },
  { key: "leave",      label: "Leave",      color: "#2563eb", bg: "rgba(37,99,235,0.12)"   },
  { key: "weekly_off", label: "Weekly Off", color: "#64748b", bg: "rgba(100,116,139,0.12)" },
  { key: "holiday",    label: "Holiday",    color: "#7c3aed", bg: "rgba(124,58,237,0.12)"  },
];

export default function HrAttendanceSummary() {
  const { data, loading, refetch } = useFetch<AttendanceSummary>(API.dashboard.hrAttendanceSummary);

  useEffect(() => {
    function handleVisibility() {
      if (document.visibilityState === "visible") refetch();
    }
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, [refetch]);

  const total = data
    ? CHIPS.reduce((sum, c) => sum + (data[c.key] ?? 0), 0)
    : 0;

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-calendar-stats" /> Today&apos;s Attendance</div>
        {!loading && total > 0 && (
          <span className="badge badge-primary">{total} employees</span>
        )}
      </div>

      {loading ? (
        <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
        </div>
      ) : !data ? (
        <div style={{ padding: "20px", textAlign: "center", fontSize: 13, color: "var(--on-variant)" }}>No data available</div>
      ) : (
        <div style={{ padding: "12px 20px 16px" }}>
          {/* Stacked bar */}
          {total > 0 && (
            <div style={{ display: "flex", height: 10, borderRadius: 6, overflow: "hidden", marginBottom: 14, gap: 1 }}>
              {CHIPS.map(c => {
                const pct = total > 0 ? ((data[c.key] ?? 0) / total) * 100 : 0;
                return pct > 0 ? (
                  <div key={c.key} title={`${c.label}: ${data[c.key]}`} style={{ width: `${pct}%`, background: c.color }} />
                ) : null;
              })}
            </div>
          )}

          {/* Chips grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
            {CHIPS.map(c => (
              <div key={c.key} style={{ display: "flex", alignItems: "center", gap: 8, padding: "7px 10px", borderRadius: 7, background: c.bg }}>
                <span style={{ fontSize: 15, fontWeight: 800, color: c.color, minWidth: 24, lineHeight: 1 }}>{data[c.key] ?? 0}</span>
                <span style={{ fontSize: 11, fontWeight: 600, color: "var(--on-bg)" }}>{c.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
