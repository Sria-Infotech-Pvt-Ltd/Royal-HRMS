"use client";

import type { PayrollCycle } from "@/types/payroll";
import { MONTHS_SHORT, STATUS_BADGE, STATUS_LABEL, DAYS_LABEL, getCalendarDates } from "./payrollDashboardShared";

interface PayrollCalendarCardProps {
  calMonth: number;
  calYear: number;
  calMonthName: string;
  calIsToday: boolean;
  calIsPast: boolean;
  calIsFuture: boolean;
  today: number;
  payDay: number;
  missedMonths: { month: number; year: number }[];
  selectedCycle: PayrollCycle | null;
  canResume: boolean;
  prevMonth: () => void;
  nextMonth: () => void;
  onSelectMissedMonth: (month: number, year: number) => void;
  onResumeCycle: (id: string, status: string, cycleStart?: string) => void;
  onRunPayroll: (month?: string, year?: string) => void;
}

export default function PayrollCalendarCard({
  calMonth, calYear, calMonthName, calIsToday, calIsPast, calIsFuture, today, payDay,
  missedMonths, selectedCycle, canResume, prevMonth, nextMonth, onSelectMissedMonth,
  onResumeCycle, onRunPayroll,
}: PayrollCalendarCardProps) {
  const { firstDay, days } = getCalendarDates(calYear, calMonth);
  const calDates = Array.from({ length: days }, (_, i) => i + 1);

  return (
    <div className="card">

      {/* Header with prev/next navigation */}
      <div className="card-header" style={{ paddingBottom: 8 }}>
        <div className="card-title" style={{ fontSize: 13 }}>
          <i className="ti ti-calendar-event" /> Payroll Calendar
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <button className="btn btn-ghost btn-sm" style={{ padding: "2px 6px" }} onClick={prevMonth}>
            <i className="ti ti-chevron-left" />
          </button>
          <span style={{ fontSize: 12, fontWeight: 600, minWidth: 100, textAlign: "center" }}>
            {calMonthName} {calYear}
          </span>
          <button className="btn btn-ghost btn-sm" style={{ padding: "2px 6px" }} onClick={nextMonth}>
            <i className="ti ti-chevron-right" />
          </button>
        </div>
      </div>

      <div className="card-body" style={{ padding: "8px 16px 16px" }}>

        {/* Missed month filter chips — shown only when cycles exist */}
        {missedMonths.length > 0 && (
          <div style={{ marginBottom: 10 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: "var(--warn)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 5 }}>
              Missing payroll
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {missedMonths.map(({ month: m, year: y }) => {
                const isSelected = calMonth === m && calYear === y;
                return (
                  <button
                    key={`${y}-${m}`}
                    onClick={() => onSelectMissedMonth(m, y)}
                    style={{
                      fontSize: 11, fontWeight: 600,
                      padding: "2px 8px", borderRadius: 20,
                      border: isSelected ? "1.5px solid var(--warn)" : "1.5px solid var(--outline-v)",
                      background: isSelected ? "rgba(var(--warn-rgb, 234,179,8), 0.12)" : "transparent",
                      color: isSelected ? "var(--warn)" : "var(--on-variant)",
                      cursor: "pointer",
                    }}
                  >
                    {MONTHS_SHORT[m]}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Calendar grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 2, marginBottom: 8 }}>
          {DAYS_LABEL.map((d, i) => (
            <div key={i} style={{ textAlign: "center", fontSize: 10, fontWeight: 600, color: "var(--on-variant)", padding: "4px 0" }}>{d}</div>
          ))}
          {Array.from({ length: firstDay }).map((_, i) => <div key={`e${i}`} />)}
          {calDates.map(d => {
            const isPayDay = d === payDay;
            const isToday  = calIsToday && d === today;
            return (
              <div
                key={d}
                style={{
                  textAlign: "center", fontSize: 11, padding: "4px 2px",
                  borderRadius: 6, fontWeight: isToday ? 700 : 400,
                  background: isPayDay ? "var(--primary)" : "transparent",
                  color:      isPayDay ? "#fff" : "var(--on-bg)",
                  border:     isToday && !isPayDay ? "1.5px solid var(--primary)" : "none",
                  opacity:    calIsPast || calIsFuture ? 0.7 : 1,
                }}
              >
                {d}
              </div>
            );
          })}
        </div>

        {/* Legend */}
        <div style={{ display: "flex", flexDirection: "column", gap: 5, borderTop: "1px solid var(--outline-v)", paddingTop: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11 }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, background: "var(--primary)" }} />
            <span>Pay Day — {payDay} {calMonthName}</span>
          </div>
          {calIsToday && (
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11 }}>
              <div style={{ width: 10, height: 10, borderRadius: 2, border: "2px solid var(--primary)" }} />
              <span>Today — {today} {calMonthName}</span>
            </div>
          )}
        </div>

        {/* Payroll status for selected month */}
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--outline-v)" }}>
          {selectedCycle ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Payroll status</span>
                <span className={STATUS_BADGE[selectedCycle.status] ?? "badge badge-neutral"}>
                  {STATUS_LABEL[selectedCycle.status] ?? selectedCycle.status}
                </span>
              </div>
              {canResume && !["paid","closed"].includes(selectedCycle.status) && (
                <button
                  className="btn btn-ghost btn-sm"
                  style={{ width: "100%", justifyContent: "center" }}
                  onClick={() => onResumeCycle(selectedCycle.id, selectedCycle.status, selectedCycle.cycle_start)}
                >
                  <i className="ti ti-arrow-right" /> Resume {calMonthName}
                </button>
              )}
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ fontSize: 12, color: calIsPast ? "var(--warn)" : "var(--on-variant)", display: "flex", alignItems: "center", gap: 6 }}>
                {calIsPast
                  ? <><i className="ti ti-alert-triangle" style={{ color: "var(--warn)" }} /> No payroll run</>
                  : calIsFuture
                  ? <><i className="ti ti-clock" /> Future month</>
                  : <><i className="ti ti-player-play" /> Ready to run</>
                }
              </div>
              {canResume && !calIsFuture && (
                <button
                  className="btn btn-filled btn-sm"
                  style={{ width: "100%", justifyContent: "center" }}
                  onClick={() => onRunPayroll(calMonthName, String(calYear))}
                >
                  <i className="ti ti-player-play" /> Run {calMonthName} Payroll
                </button>
              )}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
