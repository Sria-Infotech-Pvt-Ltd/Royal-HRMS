"use client";

// "Today" card (reference .ess-card > .ess-list): shift, weekly timesheet and
// the next holiday — each row a link into the tab it belongs to. Real data:
// the org default shift, this week's logged hours, and the holiday calendar.

import { useFetch } from "@/hooks/useFetch";
import { useWeeklyTimesheet } from "@/hooks/useWeeklyTimesheet";
import { API } from "@/lib/api/endpoints";
import type { AttendanceStatus } from "@/types/employeeDashboard";
import type { HolidayListData } from "@/types/holidays";
import type { EssTabId } from "./HomeTab";

interface Shift { name: string; start_time: string; end_time: string }

interface Props {
  status: AttendanceStatus | null;
  branch?: string;
  onNavigate: (tab: EssTabId) => void;
}

function shiftState(status: AttendanceStatus | null, shift: Shift): { label: string; ok: boolean } {
  const [startH, startM] = shift.start_time.split(":").map(Number);
  const startMinutes = startH * 60 + startM;
  if (!status?.clocked_in) {
    const now = new Date();
    const nowMinutes = now.getHours() * 60 + now.getMinutes();
    return nowMinutes < startMinutes ? { label: "UPCOMING", ok: true } : { label: "NOT CLOCKED IN", ok: false };
  }
  if (!status.clock_in_time) return { label: "ON TIME", ok: true };
  const [inH, inM] = status.clock_in_time.split(":").map(Number);
  // Same 15-minute grace the rest of the app uses.
  return inH * 60 + inM > startMinutes + 15 ? { label: "LATE", ok: false } : { label: "ON TIME", ok: true };
}

function dueDay(weekStartIso: string): string {
  const d = new Date(`${weekStartIso}T12:00:00`);
  d.setDate(d.getDate() + 4);
  return d.toLocaleDateString("en-US", { weekday: "short" }).toUpperCase();
}

export default function HomeTodayPanel({ status, branch, onNavigate }: Props) {
  const { data: shift } = useFetch<Shift | null>(API.attendance.myShift);
  const { data: timesheet } = useWeeklyTimesheet();
  const { data: holidayData } = useFetch<HolidayListData>(API.leave.holidays);

  const todayIso = new Date().toISOString().slice(0, 10);
  const nextHoliday = (holidayData?.holidays ?? [])
    .filter(h => h.is_active && h.date >= todayIso)
    .sort((a, b) => a.date.localeCompare(b.date))[0];

  const hasShift = !!shift?.start_time;
  const shiftBadge = hasShift && shift ? shiftState(status, shift) : null;

  return (
    <section className="ess-card">
      <h2>Today</h2>
      <p>Your schedule and attendance status.</p>
      <div className="ess-list">
        {hasShift && shift && shiftBadge && (
          <button type="button" className="ess-row ess-row-link" onClick={() => onNavigate("attendance")}>
            <div><b>{shift.name}</b><small>{shift.start_time}–{shift.end_time}{branch ? ` · ${branch}` : ""}</small></div>
            <span className={`state${shiftBadge.ok ? " ok" : ""}`}>{shiftBadge.label}</span>
          </button>
        )}
        {timesheet && (
          <button type="button" className="ess-row ess-row-link" onClick={() => onNavigate("attendance")}>
            <div><b>Weekly timesheet</b><small>{timesheet.hours_logged} of {timesheet.target_hours} hours logged</small></div>
            <span className={`state${timesheet.submitted ? " ok" : ""}`}>{timesheet.submitted ? "SUBMITTED" : `DUE ${dueDay(timesheet.week_start)}`}</span>
          </button>
        )}
        {nextHoliday && (
          <button type="button" className="ess-row ess-row-link" onClick={() => onNavigate("leave")}>
            <div>
              <b>Holiday</b>
              <small>{nextHoliday.name} · {new Date(`${nextHoliday.date}T12:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "long" })}</small>
            </div>
            <span className="state ok">UPCOMING</span>
          </button>
        )}
        {!hasShift && !timesheet && !nextHoliday && (
          <div className="ess-row"><div><b>Nothing scheduled</b><small>Your shift, timesheet and holidays will appear here.</small></div></div>
        )}
      </div>
    </section>
  );
}
