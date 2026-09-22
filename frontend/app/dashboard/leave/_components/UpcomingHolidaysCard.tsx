"use client";

// Real upcoming-holiday list — reuses the existing Holidays endpoint
// (already used by AttendanceCalendar's holiday coloring and the HR
// Holidays screen), branch-scoped to the current employee automatically
// by HolidayListCreateView when no `branch` param is passed.

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { useCurrentUser } from "@/hooks/useCurrentUser";

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
          <div className="card-title"><i className="ti ti-calendar-event" /> Upcoming holidays</div>
          <div className="page-sub" style={{ marginTop: 2 }}>Your {scopeLabel} holiday calendar.</div>
        </div>
      </div>
      <div className="card-body" style={{ padding: 0 }}>
        {loading ? (
          <div style={{ padding: "40px 20px", textAlign: "center" }}>
            <i className="ti ti-loader-2" style={{ fontSize: 24, color: "var(--outline-v)" }} />
          </div>
        ) : upcoming.length === 0 ? (
          <div style={{ padding: "40px 20px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
            No upcoming holidays scheduled.
          </div>
        ) : (
          upcoming.map((h, idx) => (
            <div
              key={h.id}
              style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "12px 20px",
                borderTop: idx === 0 ? "none" : "1px solid var(--outline-v)",
              }}
            >
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{h.name}</div>
                <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
                  {h.day} · {fmtHolidayDate(h.date)}
                </div>
              </div>
              <span className="badge badge-success">HOLIDAY</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
