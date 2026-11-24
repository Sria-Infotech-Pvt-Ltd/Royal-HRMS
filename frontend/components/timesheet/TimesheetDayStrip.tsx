"use client";

// A compact row of the seven days of the week: the date, a chip for holidays / weekly offs / leave / not-employed days, the project
// hours entered that day (amber over 12, red over 24), and - on its own line - the hours attendance recorded from punches.

import { useT } from "@/hooks/useI18n";
import { dailyTotals, dayChipLabel, dayNumber, formatHours, weekTotal } from "@/lib/timesheet";
import type { GridLine, TimesheetDay, TimesheetLimits } from "@/types/timesheet";

interface Props {
  days: TimesheetDay[];
  lines: GridLine[];
  limits: TimesheetLimits;
}

function hoursColour(total: number, warnAbove: number, maxAllowed: number): string {
  if (total > maxAllowed) return "var(--crit)";
  return total > warnAbove ? "var(--warn)" : "var(--ink)";
}

export default function TimesheetDayStrip({ days, lines, limits }: Props) {
  const t = useT();
  const dates = days.map(day => day.date);
  const totals = dailyTotals(lines, dates);
  const warnAbove = Number(limits.daily_warning_hours);
  const maxAllowed = Number(limits.daily_max_hours);
  return (
    <div style={{ border: "1px solid var(--line)", borderRadius: 12, background: "var(--surface)", padding: "12px 14px" }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, minmax(0, 1fr)) auto", gap: 8, alignItems: "start" }}>
        {days.map(day => {
          const chip = dayChipLabel(day);
          return (
            <div key={day.date} style={{ textAlign: "center", minWidth: 0, opacity: day.is_employed ? 1 : 0.55 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)" }}>{day.weekday} {dayNumber(day.date)}</div>
              <div style={{ minHeight: 20, marginTop: 2 }}>{chip && <span className="chip warn" style={{ fontSize: 9.5 }}>{t(chip)}</span>}</div>
              <div data-testid={`day-total-${day.date}`} style={{ fontSize: 15, fontWeight: 700, color: hoursColour(totals[day.date], warnAbove, maxAllowed) }}>
                {formatHours(totals[day.date])}
              </div>
              <div style={{ fontSize: 10.5, color: "var(--muted)" }} title={t("Hours recorded by attendance punches")}>
                {day.attendance_minutes > 0 ? t("{hours} h punched", { hours: formatHours(day.attendance_minutes / 60) }) : t("no punches")}
              </div>
            </div>
          );
        })}
        <div style={{ textAlign: "right", paddingLeft: 8, borderLeft: "1px solid var(--line-soft)" }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)" }}>{t("Week")}</div>
          <div style={{ minHeight: 20 }} />
          <div data-testid="week-total" style={{ fontSize: 15, fontWeight: 700 }}>{formatHours(weekTotal(lines, dates))}</div>
          <div style={{ fontSize: 10.5, color: "var(--muted)" }}>{t("project hours")}</div>
        </div>
      </div>
    </div>
  );
}
