"use client";

// Self-service "Attendance" tab, laid out as the Employee Directory reference: four metric tiles, this month's
// day-by-day calendar beside the latest punches, then the weekly timesheet beside attendance requests. All of it
// is real data (attendance stats/calendar/history, the weekly timesheet and the employee's correction requests);
// clocking in/out lives on the "Punch in" button in the page header, so there is no second clock widget here.

import { useMemo, useState } from "react";
import { useAttendanceDashboard } from "@/hooks/useAttendanceDashboard";
import { useFetch } from "@/hooks/useFetch";
import { useWeeklyTimesheet } from "@/hooks/useWeeklyTimesheet";
import { API } from "@/lib/api/endpoints";
import RegularizationModal from "../../my-attendance/_components/RegularizationModal";
import MyCorrectionDetailModal from "../../my-requests/_components/MyCorrectionDetailModal";
import {
  MyCorrectionRequest, PaginatedResponse, STATUS_LABEL, toDisplayStatus,
} from "../../my-requests/_data";
import type { HistoryRow } from "@/types/attendance";

const WEEKDAY_LETTER = ["S", "M", "T", "W", "T", "F", "S"];
const MONTH_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTH_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const RECENT_PUNCHES = 3;
const RECENT_REQUESTS = 5;

function dayLabel(iso: string): string {
  const [, month, day] = iso.split("-").map(Number);
  return `${day} ${MONTH_SHORT[month - 1] ?? ""}`;
}

function punchDetail(row: HistoryRow): string {
  return row.clockOut ? `In ${row.clockIn} · Out ${row.clockOut}` : `In ${row.clockIn}`;
}

function correctionTitle(dateIso: string): string {
  const date = new Date(`${dateIso}T12:00:00`);
  return Number.isNaN(date.getTime()) ? "Correction" : `${date.getDate()} ${MONTH_LONG[date.getMonth()]} correction`;
}

function dayClass(status: string | undefined): string {
  const value = (status ?? "").toLowerCase();
  if (value === "present" || value === "late") return "present";
  if (value.includes("leave")) return "leave";
  return "";
}

function TimesheetCard() {
  const { data, submitting, submit } = useWeeklyTimesheet();
  if (!data) return <div className="ess-card"><h2>Weekly timesheet</h2><p>Loading…</p></div>;
  const remaining = Math.max(0, data.target_hours - data.hours_logged);
  const weekEnding = new Date(`${data.week_end}T12:00:00`);
  const due = new Date(`${data.week_start}T12:00:00`);
  due.setDate(due.getDate() + 4);
  return (
    <div className="ess-card">
      <div className="ess-pagehead">
        <div>
          <h2>Weekly timesheet</h2>
          <p>{data.hours_logged} of {data.target_hours} hours logged for the current week.</p>
        </div>
        <button className="rvbtn pri" type="button" onClick={submit} disabled={submitting || data.submitted}>
          {data.submitted ? "Submitted" : submitting ? "Submitting…" : "Submit timesheet"}
        </button>
      </div>
      <div className="ess-list">
        <div className="ess-row">
          <div>
            <b>Week ending {weekEnding.getDate()} {MONTH_LONG[weekEnding.getMonth()]}</b>
            <small>
              {data.submitted
                ? "Submitted — thank you."
                : remaining > 0
                  ? `${remaining} hour${remaining === 1 ? "" : "s"} remaining · Submit after completing your work summary.`
                  : "Target reached — ready to submit."}
            </small>
          </div>
          <span className={`state${data.submitted ? " ok" : ""}`}>
            {data.submitted ? "SUBMITTED" : `DUE ${due.toLocaleDateString("en-US", { weekday: "short" }).toUpperCase()}`}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function EssAttendanceTab() {
  const now = new Date();
  const month = now.getMonth() + 1;
  const year = now.getFullYear();
  const { stats, calendar, history, isLoading, refetch } = useAttendanceDashboard({ month, year });
  const corrections = useFetch<PaginatedResponse<MyCorrectionRequest>>(`${API.attendance.myCorrections}?page_size=100`);
  const [showRegularize, setShowRegularize] = useState(false);
  const [detail, setDetail] = useState<MyCorrectionRequest | null>(null);

  const days = useMemo(() => Array.from({ length: now.getDate() }, (_, index) => {
    const dayNumber = index + 1;
    const iso = `${year}-${String(month).padStart(2, "0")}-${String(dayNumber).padStart(2, "0")}`;
    return { dayNumber, letter: WEEKDAY_LETTER[new Date(year, month - 1, dayNumber).getDay()], cls: dayClass(calendar[iso]?.status) };
  }), [calendar, month, year, now]);

  const punches = history.filter(row => row.clockIn).slice(0, RECENT_PUNCHES);
  const requests = [...(corrections.data?.results ?? [])]
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, RECENT_REQUESTS);

  const present = stats?.days_present ?? 0;
  const workingDays = stats?.working_days ?? 0;
  const hours = stats ? Math.round(stats.total_work_minutes / 60) : 0;

  return (
    <section className="ess-page">
      <div className="ess-pagehead">
        <div>
          <h2>Attendance</h2>
          <p>Punch status, monthly calendar and regularization requests.</p>
        </div>
        <button className="rvbtn pri" type="button" onClick={() => setShowRegularize(true)}>Regularize attendance</button>
      </div>

      <div className="ess-metrics">
        <article className="ess-metric"><i>PRESENT</i><b>{isLoading ? "—" : present}</b><span>of {workingDays} working days</span></article>
        <article className="ess-metric"><i>WORK HOURS</i><b>{isLoading ? "—" : `${hours}h`}</b><span>{stats?.work_hours_percentage ?? 0}% of expected</span></article>
        <article className="ess-metric"><i>LATE ARRIVALS</i><b>{isLoading ? "—" : stats?.late_arrivals ?? 0}</b><span>{stats?.late_arrivals_regularized ?? 0} regularized</span></article>
        <article className="ess-metric"><i>MISSING PUNCH</i><b>{isLoading ? "—" : stats?.missing_punch ?? 0}</b><span>no action required</span></article>
      </div>

      <div className="ess-grid">
        <div className="ess-card">
          <h2>{MONTH_LONG[month - 1]} {year}</h2>
          <p>Daily attendance and approved leave.</p>
          <div className="ess-calendar-wrap">
            <div className="ess-calendar">
              {days.map(day => (
                <div key={day.dayNumber} className={`ess-day ${day.cls}`}><span>{day.letter}</span><b>{day.dayNumber}</b></div>
              ))}
            </div>
          </div>
        </div>
        <div className="ess-card">
          <h2>Recent punches</h2>
          <p>Device and web attendance events.</p>
          <div className="ess-list">
            {punches.length === 0 && <div className="ess-row"><div><b>No punches yet</b><small>Your clock-ins will appear here.</small></div></div>}
            {punches.map(row => (
              <div className="ess-row" key={row.date}>
                <div><b>{dayLabel(row.date)}</b><small>{punchDetail(row)}</small></div>
                <span className="state ok">{row.clockOut ? "COMPLETE" : "PRESENT"}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="ess-grid">
        <TimesheetCard />
        <div className="ess-card">
          <h2>Attendance requests</h2>
          <p>Corrections remain visible beside original punches.</p>
          <div className="ess-list">
            {requests.length === 0 && (
              <div className="ess-row"><div><b>No correction requests yet</b><small>Use Regularize attendance if a punch was missed or recorded incorrectly.</small></div></div>
            )}
            {requests.map(request => {
              const status = toDisplayStatus(request.status);
              const approver = request.l2_approver_name || request.l1_approver_name;
              return (
                <button key={request.id} className="ess-row ess-row-link" type="button" onClick={() => setDetail(request)}>
                  <div>
                    <b>{correctionTitle(request.date)}</b>
                    <small>{status === "approved" && approver ? `Approved by ${approver}` : STATUS_LABEL[status]} · View details</small>
                  </div>
                  <span className={`state${status === "approved" ? " ok" : ""}`}>{STATUS_LABEL[status].toUpperCase()}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {showRegularize && (
        <RegularizationModal onClose={() => setShowRegularize(false)} onSuccess={() => { refetch(); corrections.refetch(); }} />
      )}
      {detail && <MyCorrectionDetailModal request={detail} onClose={() => setDetail(null)} />}
    </section>
  );
}
