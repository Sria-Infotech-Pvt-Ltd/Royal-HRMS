"use client";

import { useState } from "react";
import AttendanceCalendar from "./AttendanceCalendar";
import AttendanceHistoryTable from "./AttendanceHistoryTable";
import type { DayRecord, HistoryRow } from "@/types/attendance";

interface Props {
  month:        number;  // 1-indexed
  year:         number;
  calendar:     Record<string, DayRecord>;
  history:      HistoryRow[];
  isLoading:    boolean;
  onPrev:       () => void;
  onNext:       () => void;
  onRegularize: (date: string) => void;
  readOnly?:    boolean;
  /** Calendar-only, no Calendar/History toggle or color legend chips — matches the plain calendar card in the reference ESS Attendance layout. */
  hideControls?: boolean;
}

const MONTH_NAMES = ["January","February","March","April","May","June","July","August","September","October","November","December"];

const LEGEND = [
  { label: "Present",    bg: "var(--success-c)",          color: "var(--success)"   },
  { label: "Late",       bg: "var(--warn-c)",             color: "var(--warn)"      },
  { label: "Absent",     bg: "var(--error-c)",            color: "var(--error)"     },
  { label: "On Leave",   bg: "rgba(59,130,246,0.12)",     color: "#3b82f6"          },
  { label: "Half Day",   bg: "rgba(251,146,60,0.15)",     color: "#ea580c"          },
  { label: "Weekly Off", bg: "var(--bg-low)",             color: "var(--outline)"   },
  { label: "Holiday",    bg: "rgba(168,85,247,0.12)",     color: "#a855f7"          },
];

type Tab = "calendar" | "history";

export default function CalendarAndHistory({ month, year, calendar, history, isLoading, onPrev, onNext, onRegularize, readOnly = false, hideControls = false }: Props) {
  const [tab, setTab] = useState<Tab>("calendar");
  const effectiveTab = hideControls ? "calendar" : tab;

  return (
    <div className="card">
      <div className="card-header" style={{ flexWrap: "wrap", gap: 8 }}>
        <div>
          <div className="card-title">
            {isLoading ? "Loading…" : `${MONTH_NAMES[month - 1]} ${year}`}
          </div>
          <div className="page-sub" style={{ marginTop: 2 }}>Daily attendance and approved leave.</div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
          {!hideControls && (
            <div style={{ display: "flex", gap: 6 }}>
              <button
                onClick={() => setTab("calendar")}
                className={`btn btn-sm ${tab === "calendar" ? "btn-filled" : "btn-ghost"}`}
              >
                <i className="ti ti-calendar" /> Calendar
              </button>
              <button
                onClick={() => setTab("history")}
                className={`btn btn-sm ${tab === "history" ? "btn-filled" : "btn-ghost"}`}
              >
                <i className="ti ti-list-details" /> History
              </button>
            </div>
          )}
          <button
            className="btn btn-ghost btn-sm"
            type="button"
            onClick={onPrev}
            disabled={isLoading}
            aria-label="Previous month"
            title="Previous month"
          >
            <i className="ti ti-chevron-left" />
          </button>
          <button
            className="btn btn-ghost btn-sm"
            type="button"
            onClick={onNext}
            disabled={isLoading}
            aria-label="Next month"
            title="Next month"
          >
            <i className="ti ti-chevron-right" />
          </button>
        </div>
      </div>

      {effectiveTab === "calendar" && !hideControls && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, padding: "12px 20px" }}>
          {LEGEND.map(item => (
            <div key={item.label} style={{ display: "flex", alignItems: "center", gap: 4, padding: "2px 8px", background: item.bg, border: "1px solid var(--outline-v)", borderRadius: 6 }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: item.color, display: "inline-block" }} />
              <span style={{ fontSize: 10, fontWeight: 500, color: item.color }}>{item.label}</span>
            </div>
          ))}
        </div>
      )}

      {effectiveTab === "calendar"
        ? <AttendanceCalendar year={year} month={month} data={calendar} onRegularize={onRegularize} readOnly={readOnly} />
        : <AttendanceHistoryTable data={history} onRegularize={onRegularize} readOnly={readOnly} />}
    </div>
  );
}
