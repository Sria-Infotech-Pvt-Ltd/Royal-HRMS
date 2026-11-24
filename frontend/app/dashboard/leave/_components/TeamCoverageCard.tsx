"use client";

// Compact "Team coverage" preview — reuses the exact same real fetch
// TeamCalendar.tsx uses (GET /leave/calendar/, approved leave only,
// scope-filtered server-side by role), just rolled up into a per-day
// overlap check for the next few days instead of a full month grid.
// Consecutive days sharing the same overlap status collapse into one row
// (e.g. "21-23 September"), matching the reference layout — the full month
// view is still reachable via the Leave page's own ?tab=calendar deep link.

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { tr } from "@/lib/i18n/tr";

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

function fmtRangeLabel(start: Date, end: Date): string {
  if (start.getTime() === end.getTime()) {
    return start.toLocaleDateString("en-GB", { day: "numeric", month: "long" });
  }
  const sameMonth = start.getMonth() === end.getMonth();
  const month = end.toLocaleDateString("en-GB", { month: "long" });
  return sameMonth
    ? `${start.getDate()}-${end.getDate()} ${month}`
    : `${start.toLocaleDateString("en-GB", { day: "numeric", month: "short" })} - ${end.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}`;
}

export default function TeamCoverageCard() {
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

  const days = dates.map(d => {
    const iso = localDateString(d);
    const overlapping = events.filter(e => e.start_date <= iso && iso <= e.end_date);
    return { date: d, isAway: overlapping.length > 0, count: overlapping.length };
  });

  // Collapse consecutive days sharing the same overlap status into one row
  // (e.g. "21-23 September"), matching the reference layout's grouped rows.
  const rows: { start: Date; end: Date; isAway: boolean; maxCount: number }[] = [];
  for (const day of days) {
    const last = rows[rows.length - 1];
    if (last && last.isAway === day.isAway) {
      last.end = day.date;
      last.maxCount = Math.max(last.maxCount, day.count);
    } else {
      rows.push({ start: day.date, end: day.date, isAway: day.isAway, maxCount: day.count });
    }
  }

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title"><i className="ti ti-users" /> {tr("Team coverage")}</div>
          <div className="page-sub" style={{ marginTop: 2 }}>{tr("Demo view for planning leave before submission.")}</div>
        </div>
      </div>
      <div className="card-body" style={{ padding: 0 }}>
        {loading ? (
          <div style={{ padding: "40px 20px", textAlign: "center" }}>
            <i className="ti ti-loader-2" style={{ fontSize: 24, color: "var(--outline-v)" }} />
          </div>
        ) : (
          rows.map(row => (
            <div key={row.start.toISOString()} className={`lv-row ${row.isAway ? "lv-st-pending" : "lv-st-approved"}`}>
              <span className="lv-dot" />
              <div className="lv-row-main">
                <div className="lv-row-title">{fmtRangeLabel(row.start, row.end)}</div>
                <div className="lv-row-meta">
                  {row.isAway
                    ? `${row.maxCount === 1 ? tr("{count} team member already away", { count: row.maxCount }) : tr("{count} team members already away", { count: row.maxCount })} · ${tr("Manager review required")}`
                    : tr("No scheduled team overlap")}
                </div>
              </div>
              <span className={`badge ${row.isAway ? "badge-warn" : "badge-success"}`}>
                {row.isAway ? tr("CHECK") : tr("AVAILABLE")}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
