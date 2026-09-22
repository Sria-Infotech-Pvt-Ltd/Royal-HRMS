"use client";

// Compact "Team coverage" preview — reuses the exact same real fetch
// TeamCalendar.tsx uses (GET /leave/calendar/, approved leave only,
// scope-filtered server-side by role), just rolled up into a per-day
// overlap check for the next few days instead of a full month grid.
// Opens the full TeamCalendar in a modal for anyone who wants the whole
// month view — see the `onOpenFullCalendar` prop.

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";

interface CalEvent {
  id:            string;
  employee_name: string;
  start_date:    string;
  end_date:      string;
}

const LOOKAHEAD_DAYS = 5;

function localDateString(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function upcomingDates(): Date[] {
  const out: Date[] = [];
  const today = new Date();
  for (let i = 0; i < LOOKAHEAD_DAYS; i++) {
    const d = new Date(today);
    d.setDate(today.getDate() + i);
    out.push(d);
  }
  return out;
}

interface Props {
  onOpenFullCalendar: () => void;
}

export default function TeamCoverageCard({ onOpenFullCalendar }: Props) {
  const now = new Date();
  const dates = upcomingDates();
  const spansTwoMonths = dates[0].getMonth() !== dates[dates.length - 1].getMonth();

  const { data: monthA, loading: loadingA } = useFetch<CalEvent[]>(
    API.leave.calendar + `?year=${now.getFullYear()}&month=${now.getMonth() + 1}`
  );
  // Only fetched when the 5-day lookahead actually crosses a month boundary.
  const nextMonthDate = new Date(now.getFullYear(), now.getMonth() + 1, 1);
  const { data: monthB, loading: loadingB } = useFetch<CalEvent[]>(
    spansTwoMonths
      ? API.leave.calendar + `?year=${nextMonthDate.getFullYear()}&month=${nextMonthDate.getMonth() + 1}`
      : null
  );

  const loading = loadingA || (spansTwoMonths && loadingB);
  const events = [...(monthA ?? []), ...(monthB ?? [])];

  const rows = dates.map(d => {
    const iso = localDateString(d);
    const overlapping = events.filter(e => e.start_date <= iso && iso <= e.end_date);
    return { date: d, iso, overlapping };
  });

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title"><i className="ti ti-users" /> Team coverage</div>
          <div className="page-sub" style={{ marginTop: 2 }}>Demo view for planning leave before submission.</div>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={onOpenFullCalendar} suppressHydrationWarning>
          <i className="ti ti-calendar" /> View full team calendar
        </button>
      </div>
      <div className="card-body" style={{ padding: 0 }}>
        {loading ? (
          <div style={{ padding: "40px 20px", textAlign: "center" }}>
            <i className="ti ti-loader-2" style={{ fontSize: 24, color: "var(--outline-v)" }} />
          </div>
        ) : (
          rows.map((row, idx) => {
            const isAway = row.overlapping.length > 0;
            return (
              <div
                key={row.iso}
                style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "12px 20px",
                  borderTop: idx === 0 ? "none" : "1px solid var(--outline-v)",
                }}
              >
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>
                    {row.date.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
                    {isAway
                      ? `${row.overlapping.length} team member${row.overlapping.length === 1 ? "" : "s"} already away · Manager review required`
                      : "No scheduled team overlap"}
                  </div>
                </div>
                <span className={`badge ${isAway ? "badge-warn" : "badge-success"}`}>
                  {isAway ? "CHECK" : "AVAILABLE"}
                </span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
