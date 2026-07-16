"use client";

import { useState } from "react";
import { useAttendanceDashboard } from "@/hooks/useAttendanceDashboard";
import ClockWidget from "./_components/ClockWidget";
import CalendarAndHistory from "./_components/CalendarAndHistory";
import CorrectionModal from "./_components/CorrectionModal";

function Spinner() {
  return <i className="ti ti-loader-2" style={{ fontSize: 14, animation: "spin 1s linear infinite" }} />;
}

function todayMonthYear() {
  const now = new Date();
  return { month: now.getMonth() + 1, year: now.getFullYear() };
}

export default function MyAttendancePage() {
  const { month: initMonth, year: initYear } = todayMonthYear();
  const [month, setMonth] = useState(initMonth);
  const [year,  setYear]  = useState(initYear);
  const [correctionDate, setCorrectionDate] = useState<string | null>(null);

  const { stats, summary, calendar, history, isLoading, refetch } = useAttendanceDashboard({ month, year });

  function prev() {
    if (month === 1) { setMonth(12); setYear(y => y - 1); }
    else { setMonth(m => m - 1); }
  }

  // Forward navigation is intentionally unbounded, same as prev() — employees
  // need to browse into future months to see upcoming holidays before
  // deciding when to apply for leave, not just review past attendance.
  function next() {
    if (month === 12) { setMonth(1); setYear(y => y + 1); }
    else { setMonth(m => m + 1); }
  }

  const daysPresent  = stats?.days_present          ?? "—";
  const lateArrivals = stats?.late_arrivals         ?? "—";
  const lopPending   = stats?.lop_pending           ?? 0;
  const avgHours     = stats?.avg_hours_per_day     ?? "—";
  const workingDays  = stats?.working_days          ?? "—";
  const presentPct   = stats && stats.working_days ? (stats.days_present / stats.working_days) * 100 : 0;
  const latePct      = stats && stats.working_days ? (stats.late_arrivals / stats.working_days) * 100 : 0;
  const avgHoursPct  = stats ? Math.min((stats.avg_hours_per_day / 9) * 100, 100) : 0;
  const attPct       = stats?.attendance_percentage ?? 0;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">My Attendance</div>
          <div className="page-sub">View your personal attendance calendar and monthly summary</div>
        </div>
      </div>

      {/* Top row: ClockWidget + 4 stat cards */}
      <div style={{ display: "grid", gridTemplateColumns: "340px 1fr", gap: 16, marginBottom: 16 }}>
        <ClockWidget />

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gridTemplateRows: "1fr 1fr", gap: 12 }}>
          <div className="stat-card">
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
              <div>
                <div className="stat-label">Days Present</div>
                <div className="stat-value">{isLoading ? <Spinner /> : daysPresent}</div>
                <div className="stat-sub">{isLoading ? "" : `of ${workingDays} working days`}</div>
              </div>
              <div className="stat-icon si-success"><i className="ti ti-user-check" /></div>
            </div>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${Math.min(presentPct, 100)}%`, background: "var(--success)" }} />
            </div>
          </div>

          <div className="stat-card">
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
              <div>
                <div className="stat-label">Late Arrivals</div>
                <div className="stat-value" style={{ color: "var(--warn)" }}>{isLoading ? <Spinner /> : lateArrivals}</div>
                <div className="stat-sub">{isLoading ? "" : `${lopPending} LOP pending`}</div>
              </div>
              <div className="stat-icon si-warn"><i className="ti ti-clock-exclamation" /></div>
            </div>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${Math.min(latePct, 100)}%`, background: "var(--warn)" }} />
            </div>
          </div>

          <div className="stat-card">
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
              <div>
                <div className="stat-label">Avg Hours / Day</div>
                <div className="stat-value">{isLoading ? <Spinner /> : avgHours}</div>
                <div className="stat-sub">Required: 9.0 hrs</div>
              </div>
              <div className="stat-icon si-info"><i className="ti ti-clock" /></div>
            </div>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${avgHoursPct}%`, background: "var(--info)" }} />
            </div>
          </div>

          <div className="stat-card">
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
              <div>
                <div className="stat-label">Attendance %</div>
                <div className="stat-value" style={{ color: "var(--success)" }}>{isLoading ? <Spinner /> : stats ? `${stats.attendance_percentage}%` : "—"}</div>
                <div className="stat-sub">Above threshold</div>
              </div>
              <div className="stat-icon si-success"><i className="ti ti-chart-bar" /></div>
            </div>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${Math.min(attPct, 100)}%`, background: "var(--success)" }} />
            </div>
          </div>
        </div>
      </div>

      {/* Monthly Summary */}
      <div className="card mb-16">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-calendar-stats" /> Monthly Summary</div>
        </div>
        <div className="card-body">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 0 }}>
            {[
              { label: "Working Days", value: summary?.working_days ?? "—", color: "var(--on-bg)"   },
              { label: "Days Present", value: summary?.days_present ?? "—", color: "var(--success)" },
              { label: "Days Absent",  value: summary?.days_absent  ?? "—", color: "var(--error)"   },
              { label: "Leave Days",   value: summary?.leave_days   ?? "—", color: "var(--info)"    },
              { label: "Half Days",    value: summary?.half_days    ?? "—", color: "var(--primary)" },
              { label: "OT Hours",     value: summary?.ot_hours     ?? "—", color: "var(--success)" },
            ].map((item, idx) => (
              <div
                key={item.label}
                style={{ padding: "14px 16px", borderRight: idx < 5 ? "1px solid var(--outline-v)" : "none", textAlign: "center" }}
              >
                <div style={{ fontSize: 11, color: "var(--on-variant)", marginBottom: 6 }}>{item.label}</div>
                <div style={{ fontSize: 24, fontWeight: 700, color: item.color, fontVariantNumeric: "tabular-nums" }}>
                  {isLoading ? <Spinner /> : item.value}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Calendar and History tabs */}
      <CalendarAndHistory
        month={month}
        year={year}
        calendar={calendar}
        history={history}
        isLoading={isLoading}
        onPrev={prev}
        onNext={next}
        onRegularize={date => setCorrectionDate(date)}
      />

      <CorrectionModal
        key={correctionDate ?? ""}
        isOpen={correctionDate !== null}
        date={correctionDate ?? ""}
        onClose={() => setCorrectionDate(null)}
        onSuccess={() => { setCorrectionDate(null); refetch(); }}
      />
    </div>
  );
}
