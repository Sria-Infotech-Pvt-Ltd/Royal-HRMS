"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import CalendarGrid, { type DayRecord } from "../../my-calendar/_components/CalendarGrid";
import MonthDetail from "../../my-calendar/_components/MonthDetail";
import RegularizationModal from "./RegularizationModal";
import { API } from "@/lib/api/endpoints";
import type { CalendarApiResponse, CalendarDayApi } from "@/types/myAttendance";

interface Props {
  month:  number;  // 1-indexed (January = 1)
  year:   number;
  onPrev: () => void;
  onNext: () => void;
}

const MONTH_NAMES = ["January","February","March","April","May","June","July","August","September","October","November","December"];

const LEGEND = [
  { label: "Present",    bg: "var(--success-c)",         color: "var(--success)"   },
  { label: "Late",       bg: "var(--warn-c)",             color: "var(--warn)"      },
  { label: "Absent",     bg: "var(--error-c)",            color: "var(--error)"     },
  { label: "On Leave",   bg: "var(--info-c)",             color: "var(--info)"      },
  { label: "Half Day",   bg: "rgba(30,78,140,0.10)",      color: "var(--primary)"   },
  { label: "Weekly Off", bg: "var(--bg-low)",             color: "var(--outline)"   },
  { label: "Holiday",    bg: "var(--sec-c)",              color: "var(--secondary)" },
];

// Backend status (snake_case) → CalendarGrid DayStatus (Title Case)
const STATUS_MAP: Record<string, DayRecord["status"]> = {
  present:    "Present",
  late:       "Late",
  absent:     "Absent",
  half_day:   "Half Day",
  weekly_off: "Weekly Off",
  holiday:    "Holiday",
  on_leave:   "On Leave",
};

function buildGridData(days: Record<string, CalendarDayApi>): Record<number, DayRecord> {
  const result: Record<number, DayRecord> = {};
  for (const [dayStr, day] of Object.entries(days)) {
    const dayNum = Number(dayStr);
    result[dayNum] = {
      status:        STATUS_MAP[day.status] ?? "Absent",
      clockIn:       day.clockIn  ?? undefined,
      clockOut:      day.clockOut ?? undefined,
      hours:         day.hours    ?? undefined,
      note:          day.note     ?? undefined,
      canRegularize: day.canRegularize,
    };
  }
  return result;
}

export default function MyCalendarTab({ month, year, onPrev, onNext }: Props) {
  const { data, loading, refetch } = useFetch<CalendarApiResponse>(
    `${API.attendance.calendar}?month=${month}&year=${year}`
  );

  const [regularizeDate, setRegularizeDate] = useState<string | null>(null);

  // CalendarGrid uses 0-indexed month (same as JS Date)
  const gridMonth = month - 1;
  const gridData  = data ? buildGridData(data.calendar?.days ?? {}) : {};

  function handleRegularize(day: number) {
    const dd = String(day).padStart(2, "0");
    const mm = String(month).padStart(2, "0");
    setRegularizeDate(`${year}-${mm}-${dd}`);
  }

  return (
    <>
      <div>
        {/* Legend + month navigation */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {LEGEND.map(item => (
              <div key={item.label} style={{ display: "flex", alignItems: "center", gap: 5, padding: "3px 10px", background: item.bg, border: "1px solid var(--outline-v)", borderRadius: 6 }}>
                <span style={{ width: 7, height: 7, borderRadius: "50%", background: item.color, display: "inline-block", flexShrink: 0 }} />
                <span style={{ fontSize: 11, fontWeight: 500, color: item.color }}>{item.label}</span>
              </div>
            ))}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
            <button className="btn btn-ghost btn-sm" onClick={onPrev}>
              <i className="ti ti-chevron-left" />
            </button>
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)", minWidth: 120, textAlign: "center" }}>
              {loading ? "Loading…" : `${MONTH_NAMES[gridMonth]} ${year}`}
            </span>
            <button className="btn btn-ghost btn-sm" onClick={onNext}>
              <i className="ti ti-chevron-right" />
            </button>
          </div>
        </div>

        <div style={{ marginBottom: 16 }}>
          <CalendarGrid year={year} month={gridMonth} data={gridData} onRegularize={handleRegularize} />
        </div>

        <MonthDetail year={year} month={gridMonth} data={gridData} onRegularize={handleRegularize} />
      </div>

      {regularizeDate && (
        <RegularizationModal
          date={regularizeDate}
          onClose={() => setRegularizeDate(null)}
          onSuccess={() => { setRegularizeDate(null); refetch(); }}
        />
      )}
    </>
  );
}
