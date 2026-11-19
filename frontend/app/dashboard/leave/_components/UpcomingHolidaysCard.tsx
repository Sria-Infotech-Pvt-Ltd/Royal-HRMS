"use client";

// Real upcoming-holiday list — reuses the existing Holidays endpoint
// (already used by AttendanceCalendar's holiday coloring and the HR
// Holidays screen), branch-scoped to the current employee automatically
// by HolidayListCreateView when no `branch` param is passed.

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { tr } from "@/lib/i18n/tr";

interface ApiHoliday {
  id:       string;
  name:     string;
  date:     string; // YYYY-MM-DD
  day:      string; // "Mon", "Tue", ...
}

interface HolidaysResponse {
  holidays: ApiHoliday[];
  total:    number;
}

const UPCOMING_COUNT = 5;

function fmtHolidayDate(iso: string): string {
  return new Date(iso + "T12:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

function monthShort(iso: string): string {
  return new Date(iso + "T12:00:00").toLocaleDateString("en-GB", { month: "short" });
}

/** "Today", "Tomorrow" or "in N days" for holidays within the next month; nothing further out. */
function daysUntil(iso: string): string | null {
  const start = new Date();
  start.setHours(12, 0, 0, 0);
  const days = Math.round((new Date(iso + "T12:00:00").getTime() - start.getTime()) / 86_400_000);
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  return days > 1 && days <= 31 ? `in ${days} days` : null;
}

export default function UpcomingHolidaysCard() {
  const currentUser = useCurrentUser();
  const year = new Date().getFullYear();
  const { data, loading } = useFetch<HolidaysResponse>(`${API.leave.holidays}?year=${year}`);

  const today = new Date().toISOString().slice(0, 10);
  const upcoming = (data?.holidays ?? [])
    .filter(h => h.date >= today)
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, UPCOMING_COUNT);

  // No per-employee "state" field exists in this codebase (only `branch`,
  // which is what the holidays endpoint actually filters by) — branch is
  // the closest real substitute for the reference copy's "<state>" token.
  const scopeLabel = currentUser?.branch || "branch";

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title"><i className="ti ti-calendar-event" /> {tr("Upcoming holidays")}</div>
          <div className="page-sub" style={{ marginTop: 2 }}>{tr("Your {scope} holiday calendar.", { scope: scopeLabel })}</div>
        </div>
      </div>
      <div className="card-body" style={{ padding: 0 }}>
        {loading ? (
          <div style={{ padding: "40px 20px", textAlign: "center" }}>
            <i className="ti ti-loader-2" style={{ fontSize: 24, color: "var(--outline-v)" }} />
          </div>
        ) : upcoming.length === 0 ? (
          <div style={{ padding: "40px 20px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
            {tr("No upcoming holidays scheduled.")}
          </div>
        ) : (
          upcoming.map(h => {
            const when = daysUntil(h.date);
            return (
              <div key={h.id} className="lv-row">
                <div className="lv-date">
                  <small>{monthShort(h.date)}</small>
                  <b>{Number(h.date.slice(8, 10))}</b>
                </div>
                <div className="lv-row-main">
                  <div className="lv-row-title">{h.name}</div>
                  <div className="lv-row-meta">{h.day} · {fmtHolidayDate(h.date)}</div>
                </div>
                {when && <span className="lv-soon">{when}</span>}
                <span className="badge badge-success">{tr("HOLIDAY")}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
