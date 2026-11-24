"use client";

import { useState } from "react";
import { useAttendanceDashboard } from "@/hooks/useAttendanceDashboard";
import CalendarAndHistory from "./CalendarAndHistory";
import CorrectionModal from "./CorrectionModal";
import RecentPunchesCard from "./RecentPunchesCard";
import { tr } from "@/lib/i18n/tr";

function Spinner() {
  return <i className="ti ti-loader-2" style={{ fontSize: 14, animation: "spin 1s linear infinite" }} />;
}

function todayMonthYear() {
  const now = new Date();
  return { month: now.getMonth() + 1, year: now.getFullYear() };
}

export default function AttendanceTab() {
  const { month: initMonth, year: initYear } = todayMonthYear();
  const [month, setMonth] = useState(initMonth);
  const [year,  setYear]  = useState(initYear);
  const [correctionDate, setCorrectionDate] = useState<string | null>(null);

  const { stats, calendar, history, isLoading, refetch } = useAttendanceDashboard({ month, year });

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

  const daysPresent   = stats?.days_present          ?? "—";
  const lateArrivals  = stats?.late_arrivals         ?? "—";
  const workingDays   = stats?.working_days          ?? "—";
  const missingPunch  = stats?.missing_punch         ?? "—";
  const regularized   = stats?.late_arrivals_regularized ?? 0;
  const workHours     = stats ? `${Math.round(stats.total_work_minutes / 60)}h` : "—";
  const workHoursPct  = stats?.work_hours_percentage ?? 0;

  return (
    <div>
      {/* Top row: 4 plain stat tiles */}
      <div className="attendance-top-row" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 12, marginBottom: 16 }}>
        <div className="stat-card">
          <div className="stat-label">{tr("Present")}</div>
          <div className="stat-value">{isLoading ? <Spinner /> : daysPresent}</div>
          <div className="stat-sub">{isLoading ? "" : tr("of {workingDays} working days", { workingDays: workingDays })}</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">{tr("Work Hours")}</div>
          <div className="stat-value">{isLoading ? <Spinner /> : workHours}</div>
          <div className="stat-sub">{isLoading ? "" : tr("{workHoursPct}% of expected", { workHoursPct: workHoursPct })}</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">{tr("Late Arrivals")}</div>
          <div className="stat-value" style={{ color: "var(--warn)" }}>{isLoading ? <Spinner /> : lateArrivals}</div>
          <div className="stat-sub">{isLoading ? "" : tr("{count} regularized", { count: regularized })}</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">{tr("Missing Punch")}</div>
          <div className="stat-value" style={{ color: "var(--error)" }}>{isLoading ? <Spinner /> : missingPunch}</div>
          <div className="stat-sub">{tr("no action required")}</div>
        </div>
      </div>

      {/* Calendar + Recent punches */}
      <div className="attendance-mid-row" style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16, alignItems: "stretch" }}>
        <CalendarAndHistory
          month={month}
          year={year}
          calendar={calendar}
          history={history}
          isLoading={isLoading}
          onPrev={prev}
          onNext={next}
          onRegularize={date => setCorrectionDate(date)}
          hideControls
        />
        <RecentPunchesCard />
      </div>

      <CorrectionModal
        key={correctionDate ?? ""}
        isOpen={correctionDate !== null}
        date={correctionDate ?? ""}
        onClose={() => setCorrectionDate(null)}
        onSuccess={() => { setCorrectionDate(null); refetch(); }}
      />

      <style jsx>{`
        @media (max-width: 768px) {
          .attendance-top-row,
          .attendance-mid-row {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
}
