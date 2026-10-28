"use client";

// Self-service "Attendance" tab, laid out exactly as the ESS reference: this
// month's day-by-day calendar beside the latest punches, then the weekly
// timesheet beside attendance requests — no metric-tile row (that belongs to
// Payslips' own reference screen, not this one). All of it is real data
// (attendance stats/calendar/history, the weekly timesheet and the
// employee's correction requests); clocking in/out lives on the "Punch in"
// button in the shared hero banner, so there is no second clock widget here.

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
import type { RecentPunchRow } from "@/types/attendance";

const WEEKDAY_LETTER = ["S", "M", "T", "W", "T", "F", "S"];
const MONTH_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const RECENT_PUNCHES = 3;
const RECENT_REQUESTS = 5;

function punchDetail(row: RecentPunchRow): string {
  return row.clockOut ? `In ${row.clockIn} · Out ${row.clockOut}` : `In ${row.clockIn} · ${row.source}`;
}

function correctionTitle(dateIso: string): string {
  const date = new Date(`${dateIso}T12:00:00`);
  return Number.isNaN(date.getTime()) ? "Correction" : `${date.getDate()} ${MONTH_LONG[date.getMonth()]} correction`;
}

function dayClass(status: string | undefined): string {
  const value = (status ?? "").toLowerCase();
  if (value === "present") return "present";
  if (value === "late") return "late";
  if (value === "absent") return "absent";
  if (value === "half day") return "half-day";
  if (value.includes("leave")) return "leave";
  if (value === "weekly off") return "weekly-off";
  if (value === "holiday") return "holiday";
  if (value === "incomplete" || value === "missing clock out") return "incomplete";
  if (value === "not joined") return "not-joined";
  return "unrecorded";
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
  const [displayedMonth, setDisplayedMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const month = displayedMonth.getMonth() + 1;
  const year = displayedMonth.getFullYear();
  const { calendar, isLoading: attendanceLoading, refetch } = useAttendanceDashboard({ month, year });
  // Dedicated recent-punches endpoint (date + location + source), not the
  // calendar dashboard's generic `history` list — that one has no location/
  // source fields at all, which is why this card was always missing them.
  const recentPunches = useFetch<RecentPunchRow[]>(`${API.attendance.recentPunches}?limit=${RECENT_PUNCHES}`);
  const corrections = useFetch<PaginatedResponse<MyCorrectionRequest>>(`${API.attendance.myCorrections}?page_size=100`);
  const [showRegularize, setShowRegularize] = useState(false);
  const [detail, setDetail] = useState<MyCorrectionRequest | null>(null);

  function changeMonth(offset: number) {
    setDisplayedMonth(current => new Date(current.getFullYear(), current.getMonth() + offset, 1));
  }

  const days = useMemo(() => {
    // The whole month, not just "1..today" — a monthly calendar that stops
    // at today hides the rest of the month's weekly-offs/holidays entirely.
    // Days with no calendar entry yet (future, unprocessed) just render
    // blank, same as any other day dayClass() doesn't recognize a status for.
    const daysInMonth = new Date(year, month, 0).getDate();
    return Array.from({ length: daysInMonth }, (_, index) => {
      const dayNumber = index + 1;
      // calendar.days is keyed by plain day-of-month ("1", "2", …), not an ISO
      // date string — same convention AttendanceCalendar.tsx's own `data[String(day)]`
      // lookup already relies on; building an ISO key here instead meant this
      // calendar never matched anything and every day rendered blank.
      const record = calendar[String(dayNumber)];
      return {
        dayNumber,
        letter: WEEKDAY_LETTER[new Date(year, month - 1, dayNumber).getDay()],
        cls: dayClass(record?.status),
        status: record?.status ?? "",
      };
    });
  }, [calendar, month, year]);

  const punches = recentPunches.data ?? [];
  const requests = [...(corrections.data?.results ?? [])]
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, RECENT_REQUESTS);

  return (
    <section className="ess-page">
      <div className="ess-pagehead">
        <div>
          <h2>Attendance</h2>
          <p>Punch status, monthly calendar and regularization requests.</p>
        </div>
        <button className="rvbtn pri" type="button" onClick={() => setShowRegularize(true)}>Regularize attendance</button>
      </div>

      <div className="ess-grid">
        <div className="ess-card">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 4 }}>
            <h2>{MONTH_LONG[month - 1]} {year}</h2>
            <div style={{ display: "flex", gap: 6 }}>
              <button
                className="rvbtn"
                type="button"
                onClick={() => changeMonth(-1)}
                disabled={attendanceLoading}
                aria-label="Previous month"
              >
                <i className="ti ti-chevron-left" /> Previous
              </button>
              <button
                className="rvbtn"
                type="button"
                onClick={() => changeMonth(1)}
                disabled={attendanceLoading}
                aria-label="Next month"
              >
                Next <i className="ti ti-chevron-right" />
              </button>
            </div>
          </div>
          <p>Daily attendance and approved leave.</p>
          <div className="ess-calendar-legend" aria-label="Attendance status colors">
            {[
              ["present", "Present"],
              ["late", "Late"],
              ["absent", "Absent"],
              ["half-day", "Half day"],
              ["leave", "On leave"],
              ["unrecorded", "Week off / Holiday"],
              ["incomplete", "Incomplete"],
              ["not-joined", "Not joined"],
            ].map(([className, label]) => (
              <span key={className}>
                <i className={`ess-status-dot ${className}`} />
                {label}
              </span>
            ))}
          </div>
          <div className="ess-calendar-wrap">
            <div className="ess-calendar">
              {days.map(day => (
                <div
                  key={day.dayNumber}
                  className={`ess-day ${day.cls}`}
                  title={day.status ? `${day.dayNumber} ${MONTH_LONG[month - 1]}: ${day.status}` : undefined}
                  aria-label={`${day.dayNumber} ${MONTH_LONG[month - 1]}${day.status ? `: ${day.status}` : ""}`}
                >
                  <span>{day.letter}</span>
                  <b>{day.dayNumber}</b>
                  {day.status && <small>{day.status}</small>}
                </div>
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
              // row.date is already a display string ("14 Oct") from the
              // backend, not an ISO date — rendered as-is, not re-parsed.
              <div className="ess-row" key={row.date}>
                <div><b>{row.date} · {row.location}</b><small>{punchDetail(row)}</small></div>
                <span className="state ok">{row.status}</span>
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
