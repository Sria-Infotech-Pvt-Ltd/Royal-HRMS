"use client";

import { useMemo } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { Holiday, HolidayListData } from "@/types/holidays";

const UPCOMING_COUNT = 3;

function fmtDate(iso: string): string {
  return new Date(iso + "T12:00:00").toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

function daysUntil(iso: string): number {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const target = new Date(iso + "T00:00:00");
  return Math.round((target.getTime() - today.getTime()) / 86_400_000);
}

export default function EmpUpcomingHolidays() {
  const { data, loading } = useFetch<HolidayListData>(API.leave.holidays);

  const upcoming = useMemo(() => {
    const todayIso = new Date().toISOString().slice(0, 10);
    return (data?.holidays ?? [])
      .filter((h: Holiday) => h.is_active && h.date >= todayIso)
      .sort((a, b) => a.date.localeCompare(b.date))
      .slice(0, UPCOMING_COUNT);
  }, [data]);

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-calendar-event" /> Upcoming Holidays</div>
      </div>

      {loading ? (
        <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
        </div>
      ) : upcoming.length === 0 ? (
        <div style={{ padding: "24px 20px", textAlign: "center", fontSize: 13, color: "var(--on-variant)" }}>
          No upcoming holidays scheduled.
        </div>
      ) : (
        <div style={{ padding: "4px 0 8px" }}>
          {upcoming.map(h => (
            <div key={h.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 20px", borderBottom: "1px solid var(--border)" }}>
              <div style={{ width: 38, height: 38, borderRadius: 8, flexShrink: 0, background: "rgba(124,58,237,0.12)", color: "#7c3aed", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
                <span style={{ fontSize: 13, fontWeight: 800, lineHeight: 1 }}>{fmtDate(h.date).split(" ")[0]}</span>
                <span style={{ fontSize: 9, textTransform: "uppercase" }}>{fmtDate(h.date).split(" ")[1]}</span>
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{h.name}</div>
                <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{h.day} · {h.holiday_type_display}</div>
              </div>
              <span className="badge badge-neutral" style={{ fontSize: 10, whiteSpace: "nowrap", flexShrink: 0 }}>
                {daysUntil(h.date) === 0 ? "Today" : `In ${daysUntil(h.date)}d`}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
