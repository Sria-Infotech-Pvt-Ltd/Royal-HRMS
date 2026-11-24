"use client";

// "Weekly timesheet" card. Hours logged this week come from real attendance records; the button opens the real weekly
// timesheet (hours per project per day, manager approval). Shared between the ESS Home ("Today" panel row) and the
// My Attendance page (full card) — see the `compact` prop.

import { tr } from "@/lib/i18n/tr";
import TimesheetCardAction from "@/components/timesheet/TimesheetCardAction";
import { useWeeklyTimesheet } from "@/hooks/useWeeklyTimesheet";
import { dueDayLabel, timesheetCardState } from "@/lib/timesheet";

function weekEndingLabel(weekEndIso: string): string {
  return new Date(weekEndIso + "T12:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "long" });
}

export default function WeeklyTimesheetCard({ compact = false }: { compact?: boolean }) {
  const { data } = useWeeklyTimesheet();
  if (!data) return null;

  const card = timesheetCardState(data, dueDayLabel(data.week_start));

  if (compact) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 0", borderBottom: "1px solid var(--outline-v)" }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--on-bg)" }}>{tr("Weekly timesheet")}</div>
          <div style={{ fontSize: 11.5, color: "var(--on-variant)" }}>{tr("{logged} of {target} hours logged", { logged: data.hours_logged, target: data.target_hours })}</div>
        </div>
        <span className={`badge ${card.badgeClass}`}>{card.badge}</span>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="page-header" style={{ padding: "18px 20px 4px" }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 15 }}>{tr("Weekly timesheet")}</div>
          <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 2 }}>
            {tr("{logged} of {target} hours logged for the current week.", { logged: data.hours_logged, target: data.target_hours })}
          </div>
        </div>
        <TimesheetCardAction summary={data} className="btn btn-filled btn-sm" />
      </div>
      <div style={{ padding: "8px 20px 20px" }}>
        <div style={{ fontWeight: 600, fontSize: 13, color: "var(--on-bg)" }}>{tr("Week ending {date}", { date: weekEndingLabel(data.week_end) })}</div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 4 }}>
          <div style={{ fontSize: 12, color: "var(--on-variant)" }}>{card.subtitle}</div>
          <span className={`badge ${card.badgeClass}`}>{card.badge}</span>
        </div>
      </div>
    </div>
  );
}
