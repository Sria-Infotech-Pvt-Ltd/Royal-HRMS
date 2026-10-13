"use client";

// Right-column "Today" panel — real shift (org default WorkingHoursPolicy,
// via the new /attendance/my-shift/ endpoint — there's no per-employee shift
// assignment field yet, so this is honestly the org-wide default, not a
// per-person value) with a derived on-time/late/upcoming status, and the
// next real upcoming holiday. No "weekly timesheet hours logged" row here —
// this app has no timesheet-submission feature to source that from, so it's
// left out rather than shown with a fabricated number.

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { AttendanceStatus } from "@/types/employeeDashboard";
import type { HolidayListData } from "@/types/holidays";
import WeeklyTimesheetCard from "./WeeklyTimesheetCard";

interface Shift {
  name: string;
  start_time: string;
  end_time: string;
}

interface Props {
  status: AttendanceStatus | null;
}

function shiftBadge(status: AttendanceStatus | null, shift: Shift): { label: string; tone: "ok" | "warn" | "neutral" } {
  if (!status?.clocked_in) {
    const now = new Date();
    const [startH, startM] = shift.start_time.split(":").map(Number);
    const startMinutes = startH * 60 + startM;
    const nowMinutes = now.getHours() * 60 + now.getMinutes();
    return nowMinutes < startMinutes ? { label: "UPCOMING", tone: "neutral" } : { label: "NOT CLOCKED IN", tone: "warn" };
  }
  if (!status.clock_in_time) return { label: "ON TIME", tone: "ok" };
  const [inH, inM] = status.clock_in_time.split(":").map(Number);
  const [startH, startM] = shift.start_time.split(":").map(Number);
  const late = inH * 60 + inM > startH * 60 + startM + 15; // matches this app's own grace-period convention elsewhere
  return late ? { label: "LATE", tone: "warn" } : { label: "ON TIME", tone: "ok" };
}

const BADGE_CLASS: Record<"ok" | "warn" | "neutral", string> = {
  ok: "badge-success", warn: "badge-warn", neutral: "badge-neutral",
};

export default function HomeTodayPanel({ status }: Props) {
  const { data: shift } = useFetch<Shift | null>(API.attendance.myShift);
  const { data: holidayData } = useFetch<HolidayListData>(API.leave.holidays);

  const todayIso = new Date().toISOString().slice(0, 10);
  const nextHoliday = (holidayData?.holidays ?? [])
    .filter(h => h.is_active && h.date >= todayIso)
    .sort((a, b) => a.date.localeCompare(b.date))[0];

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-calendar-time" /> Today</div>
      </div>
      <div style={{ padding: "4px 20px 16px", fontSize: 12, color: "var(--on-variant)" }}>
        Your schedule and attendance status.
      </div>
      <div style={{ padding: "0 20px 16px" }}>
        {/* The backend's success() envelope turns a "no default shift
            configured" response's data=None into data:{} (an empty
            object), not null — so `shift` alone being truthy doesn't mean
            it has real fields. Check for an actual field instead. */}
        {!!shift?.start_time && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 0", borderBottom: "1px solid var(--outline-v)" }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: "var(--on-bg)" }}>{shift.name}</div>
              <div style={{ fontSize: 11.5, color: "var(--on-variant)" }}>{shift.start_time}–{shift.end_time}</div>
            </div>
            {(() => { const b = shiftBadge(status, shift); return <span className={`badge ${BADGE_CLASS[b.tone]}`}>{b.label}</span>; })()}
          </div>
        )}
        <WeeklyTimesheetCard compact />
        {nextHoliday && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 0" }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: "var(--on-bg)" }}>{nextHoliday.name}</div>
              <div style={{ fontSize: 11.5, color: "var(--on-variant)" }}>
                {new Date(nextHoliday.date + "T12:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "long" })}
              </div>
            </div>
            <span className="badge badge-neutral">UPCOMING</span>
          </div>
        )}
        {!shift?.start_time && !nextHoliday && (
          <div style={{ fontSize: 12.5, color: "var(--on-variant)", padding: "10px 0" }}>Nothing scheduled to show yet.</div>
        )}
      </div>
    </div>
  );
}
