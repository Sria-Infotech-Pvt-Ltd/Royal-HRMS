"use client";

// Self-service "Attendance" tab, laid out exactly as the ESS reference: this
// month's day-by-day calendar beside the latest punches, then the weekly
// timesheet beside attendance requests — no metric-tile row (that belongs to
// Payslips' own reference screen, not this one). All of it is real data
// (attendance stats/calendar/history, the weekly timesheet and the
// employee's correction requests); clocking in/out lives on the "Punch in"
// button in the shared hero banner, so there is no second clock widget here.

import { useState } from "react";
import { useAttendanceDashboard } from "@/hooks/useAttendanceDashboard";
import { useFetch } from "@/hooks/useFetch";
import { useWeeklyTimesheet } from "@/hooks/useWeeklyTimesheet";
import { API } from "@/lib/api/endpoints";
import { dueDayLabel, timesheetCardState } from "@/lib/timesheet";
import TimesheetCardAction from "@/components/timesheet/TimesheetCardAction";
import RegularizationModal from "../../my-attendance/_components/RegularizationModal";
import MyCorrectionDetailModal from "../../my-requests/_components/MyCorrectionDetailModal";
import WfhRequestModal from "../../work-from-home/_components/WfhRequestModal";
import WfhRequestDetailModal from "../../work-from-home/_components/WfhRequestDetailModal";
import { MyCorrectionRequest, PaginatedResponse } from "../../my-requests/_data";
import type { RecentPunchRow } from "@/types/attendance";
import type { WorkFromHomeRequest } from "@/types/workFromHome";
import AttendanceRequestsCard from "./AttendanceRequestsCard";
import EssAttendanceCalendar from "./EssAttendanceCalendar";
import { MONTH_LONG, buildAttendanceRequestRows } from "./attendanceRequestRows";

const RECENT_PUNCHES = 3;
const RECENT_REQUESTS = 5;

function punchDetail(row: RecentPunchRow): string {
  return row.clockOut ? `In ${row.clockIn} · Out ${row.clockOut}` : `In ${row.clockIn} · ${row.source}`;
}

function TimesheetCard({ isReadOnly, onOpen }: { isReadOnly: boolean; onOpen?: (weekStart: string) => void }) {
  const { data } = useWeeklyTimesheet();
  if (!data) return <div className="ess-card"><h2>Weekly timesheet</h2><p>Loading…</p></div>;
  const weekEnding = new Date(`${data.week_end}T12:00:00`);
  const card = timesheetCardState(data, dueDayLabel(data.week_start));
  return (
    <div className="ess-card">
      <div className="ess-pagehead">
        <div>
          <h2>Weekly timesheet</h2>
          <p>{data.hours_logged} of {data.target_hours} hours logged for the current week.</p>
        </div>
        {!isReadOnly && <TimesheetCardAction summary={data} className="rvbtn pri" onOpen={onOpen} />}
      </div>
      <div className="ess-list">
        <div className="ess-row">
          <div>
            <b>Week ending {weekEnding.getDate()} {MONTH_LONG[weekEnding.getMonth()]}</b>
            <small>{card.subtitle}</small>
          </div>
          <span className={`state${card.isDone ? " ok" : ""}`}>{card.badge}</span>
        </div>
      </div>
    </div>
  );
}

/** `isReadOnly`: an admin viewing someone else's workspace. The server honours "view as" for reads only, so a WFH request
 *  made from there would be filed on the admin's own account; the entry is hidden instead. */
export default function EssAttendanceTab({ isReadOnly = false, onViewAllRequests, onOpenTimesheet }: { isReadOnly?: boolean; onViewAllRequests?: () => void; onOpenTimesheet?: (weekStart: string) => void }) {
  const [displayedMonth, setDisplayedMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const month = displayedMonth.getMonth() + 1;
  const year = displayedMonth.getFullYear();
  const { calendar, isLoading: attendanceLoading, error: attendanceError, refetch } = useAttendanceDashboard({ month, year });
  // Dedicated recent-punches endpoint (date + location + source), not the
  // calendar dashboard's generic `history` list — that one has no location/
  // source fields at all, which is why this card was always missing them.
  const recentPunches = useFetch<RecentPunchRow[]>(`${API.attendance.recentPunches}?limit=${RECENT_PUNCHES}`);
  const corrections = useFetch<PaginatedResponse<MyCorrectionRequest>>(`${API.attendance.myCorrections}?page_size=100`);
  const wfh = useFetch<PaginatedResponse<WorkFromHomeRequest>>(`${API.workFromHome.requests}?page_size=100`);
  const [showRegularize, setShowRegularize] = useState(false);
  const [showWfh, setShowWfh] = useState(false);
  const [detail, setDetail] = useState<MyCorrectionRequest | null>(null);
  const [wfhDetail, setWfhDetail] = useState<WorkFromHomeRequest | null>(null);

  function changeMonth(offset: number) {
    setDisplayedMonth(current => new Date(current.getFullYear(), current.getMonth() + offset, 1));
  }

  function goToCurrentMonth() {
    const now = new Date();
    setDisplayedMonth(new Date(now.getFullYear(), now.getMonth(), 1));
  }

  const punches = recentPunches.data ?? [];
  const requestRows = buildAttendanceRequestRows(corrections.data?.results ?? [], wfh.data?.results ?? [], RECENT_REQUESTS);

  return (
    <section className="ess-page">
      <div className="ess-pagehead">
        <div>
          <h2>Attendance</h2>
          <p>Punch status, monthly calendar, regularization and work-from-home requests.</p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {!isReadOnly && (
            <button className="rvbtn" type="button" onClick={() => setShowWfh(true)}>
              <i className="ti ti-home-2" aria-hidden="true" /> Request work from home
            </button>
          )}
          <button className="rvbtn pri" type="button" onClick={() => setShowRegularize(true)}>Regularize attendance</button>
        </div>
      </div>

      {/* Without this a failed load drew an empty calendar that looked like "nothing was marked". */}
      {attendanceError && (
        <div className="alert alert-error" role="alert" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
          <span>Could not load your attendance for this month ({attendanceError}). Your records are not lost; this is only the screen failing to load them.</span>
          <button className="rvbtn" type="button" onClick={refetch}>Try again</button>
        </div>
      )}

      <div className="ess-grid">
        <div className="ess-card">
          <EssAttendanceCalendar
            year={year}
            month={month}
            calendar={calendar}
            isLoading={attendanceLoading}
            onPreviousMonth={() => changeMonth(-1)}
            onNextMonth={() => changeMonth(1)}
            onToday={goToCurrentMonth}
          />
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
        <TimesheetCard isReadOnly={isReadOnly} onOpen={onOpenTimesheet} />
        <AttendanceRequestsCard rows={requestRows} onOpenCorrection={setDetail} onOpenWfh={setWfhDetail} onViewAll={onViewAllRequests} />
      </div>

      {showRegularize && (
        <RegularizationModal onClose={() => setShowRegularize(false)} onSuccess={() => { refetch(); corrections.refetch(); }} />
      )}
      {/* The form shows its own "Request Submitted" screen. A new WFH request is pending, so it changes no punches or
          calendar day yet (only an approved one does); only the request list needs refreshing. */}
      {showWfh && <WfhRequestModal onClose={() => setShowWfh(false)} onCreated={() => wfh.refetch()} />}
      {detail && <MyCorrectionDetailModal request={detail} onClose={() => setDetail(null)} />}
      {wfhDetail && <WfhRequestDetailModal request={wfhDetail} onClose={() => setWfhDetail(null)} onChanged={() => wfh.refetch()} readOnly={isReadOnly} />}
    </section>
  );
}
