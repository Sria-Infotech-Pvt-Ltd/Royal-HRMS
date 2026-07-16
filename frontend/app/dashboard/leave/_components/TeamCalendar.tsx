"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { LeaveTypeKey, LEAVE_TYPE_CONFIG } from "../_data";

interface CalEvent {
  id:                  string;
  employee_name:       string;
  employee_code:       string;
  leave_type:          LeaveTypeKey;
  leave_type_display:  string;
  start_date:          string;
  end_date:            string;
  total_days:          number;
}

const MONTH_NAMES = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const DAY_NAMES   = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];

function eventColor(leaveType: LeaveTypeKey): string {
  return LEAVE_TYPE_CONFIG[leaveType]?.color ?? "#1e4e8c";
}

function dayEvents(events: CalEvent[], year: number, month: number, day: number): CalEvent[] {
  const date = new Date(year, month, day);
  return events.filter(e => {
    const start = new Date(e.start_date + "T00:00:00");
    const end   = new Date(e.end_date   + "T00:00:00");
    return date >= start && date <= end;
  });
}

export default function TeamCalendar() {
  const now = new Date();
  const [year,  setYear]  = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());

  const { data: events, loading } = useFetch<CalEvent[]>(
    API.leave.calendar + `?year=${year}&month=${month + 1}`
  );

  const allEvents = events ?? [];

  const firstDay    = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const cells: Array<number | null> = [
    ...Array<null>(firstDay).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);

  const today          = now.getDate();
  const isCurrentMonth = now.getFullYear() === year && now.getMonth() === month;

  function prev() {
    if (month === 0) { setMonth(11); setYear(y => y - 1); }
    else setMonth(m => m - 1);
  }
  function next() {
    if (month === 11) { setMonth(0); setYear(y => y + 1); }
    else setMonth(m => m + 1);
  }

  const usedTypes = [...new Set(allEvents.map(e => e.leave_type))];

  return (
    <div className="w-full flex flex-col gap-5">

      {/* Legend */}
      {usedTypes.length > 0 && (
        <div className="flex gap-4 flex-wrap">
          {usedTypes.map(type => (
            <div key={type} className="flex items-center gap-2 text-xs text-gray-500">
              <div className="w-3 h-3 rounded" style={{ background: eventColor(type) }} />
              {LEAVE_TYPE_CONFIG[type]?.label ?? type}
            </div>
          ))}
        </div>
      )}

      {/* Calendar card */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <button onClick={prev} className="w-8 h-8 rounded-lg border border-gray-200 flex items-center justify-center text-gray-500 hover:bg-gray-50 transition-colors">
            <i className="ti ti-chevron-left text-sm" />
          </button>
          <span className="text-sm font-bold text-[#1a2b4a]">{MONTH_NAMES[month]} {year}</span>
          <button onClick={next} className="w-8 h-8 rounded-lg border border-gray-200 flex items-center justify-center text-gray-500 hover:bg-gray-50 transition-colors">
            <i className="ti ti-chevron-right text-sm" />
          </button>
        </div>

        {/* Day name headers */}
        <div className="grid grid-cols-7 border-b border-gray-100 bg-gray-50">
          {DAY_NAMES.map(d => (
            <div key={d} className="py-2.5 text-center text-xs font-semibold text-gray-400 uppercase tracking-wider">{d}</div>
          ))}
        </div>

        {/* Grid */}
        {loading ? (
          <div style={{ padding: "60px 20px", textAlign: "center" }}>
            <i className="ti ti-loader-2" style={{ fontSize: 28, color: "var(--outline-v)" }} />
          </div>
        ) : (
          <div className="grid grid-cols-7">
            {cells.map((day, idx) => {
              const ev        = day ? dayEvents(allEvents, year, month, day) : [];
              const isToday   = isCurrentMonth && day === today;
              const isWeekend = idx % 7 === 0 || idx % 7 === 6;
              const showRight = idx % 7 !== 6;
              const showBot   = idx < cells.length - 7;

              return (
                <div
                  key={idx}
                  className={[
                    "min-h-[90px] p-2",
                    showRight ? "border-r border-gray-100" : "",
                    showBot   ? "border-b border-gray-100" : "",
                    !day         ? "bg-gray-50"   :
                    isWeekend    ? "bg-gray-50/50" : "bg-white",
                  ].join(" ")}
                >
                  {day && (
                    <>
                      <div className={[
                        "w-6 h-6 rounded-full flex items-center justify-center text-xs mb-1 font-medium",
                        isToday ? "bg-[#1e4e8c] text-white font-bold" : isWeekend ? "text-gray-400" : "text-gray-600",
                      ].join(" ")}>
                        {day}
                      </div>
                      <div className="flex flex-col gap-0.5">
                        {ev.slice(0, 2).map((e, i) => (
                          <div
                            key={i}
                            title={`${e.employee_name} – ${e.leave_type_display}`}
                            className="text-white text-[10px] font-medium px-1.5 py-0.5 rounded truncate"
                            style={{ background: eventColor(e.leave_type) }}
                          >
                            {e.employee_name.split(" ")[0]}
                          </div>
                        ))}
                        {ev.length > 2 && <div className="text-[10px] text-gray-400 pl-1">+{ev.length - 2}</div>}
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Event list */}
      {allEvents.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="flex items-center gap-2 px-6 py-4 border-b border-gray-100 text-sm font-semibold text-[#1a2b4a]">
            <i className="ti ti-calendar-event text-[#1e4e8c]" /> Leaves this month
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-100">
                  <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase">Employee</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Type</th>
                  <th className="text-center px-4 py-3 text-xs font-semibold text-gray-500 uppercase">From</th>
                  <th className="text-center px-4 py-3 text-xs font-semibold text-gray-500 uppercase">To</th>
                  <th className="text-center px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Days</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {allEvents.map(e => (
                  <tr key={e.id} className="hover:bg-gray-50">
                    <td className="px-6 py-3.5 font-semibold text-[#1a2b4a]">{e.employee_name}</td>
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-2">
                        <div className="w-2.5 h-2.5 rounded-full" style={{ background: eventColor(e.leave_type) }} />
                        <span className="text-gray-600">{e.leave_type_display}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3.5 text-center text-gray-600">
                      {new Date(e.start_date + "T12:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                    </td>
                    <td className="px-4 py-3.5 text-center text-gray-600">
                      {new Date(e.end_date + "T12:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                    </td>
                    <td className="px-4 py-3.5 text-center font-bold text-[#1e4e8c]">{e.total_days}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!loading && allEvents.length === 0 && (
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-10 text-center">
          <i className="ti ti-calendar-off" style={{ fontSize: 32, color: "var(--outline-v)", display: "block", marginBottom: 8 }} />
          <p style={{ color: "var(--on-variant)", fontSize: 13 }}>No approved leaves for {MONTH_NAMES[month]} {year}.</p>
        </div>
      )}
    </div>
  );
}
