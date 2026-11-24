"use client";

import TimesheetStatusBadge from "@/components/timesheet/TimesheetStatusBadge";
import { addDays, currentMonday, weekRangeLabel } from "@/lib/timesheet";
import type { TimesheetWeekView } from "@/types/timesheet";
import { useT } from "@/hooks/useI18n";

interface Props {
  view: TimesheetWeekView;
  onGoToWeek: (weekStart: string) => void;
}

function dueText(dueIso: string): string {
  return new Date(`${dueIso}T12:00:00`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
}

export default function TimesheetHeader({ view, onGoToWeek }: Props) {
  const t = useT();
  const thisWeek = currentMonday();
  const isCurrentOrLater = view.week_start >= thisWeek;
  return (
    <div className="ess-pagehead" style={{ alignItems: "center", flexWrap: "wrap", gap: 12 }}>
      <div>
        <h2 style={{ margin: 0 }}>{weekRangeLabel(view.week_start, view.week_end)}</h2>
        <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--muted)" }}>
          {t("Due {date}", { date: dueText(view.due_date) })}{view.approver ? ` · ${t("Approver: {name}", { name: view.approver.name })}` : ""}
        </p>
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <TimesheetStatusBadge status={view.status} isLate={view.is_late} />
        <button type="button" className="rvbtn" aria-label={t("Previous week")} onClick={() => onGoToWeek(addDays(view.week_start, -7))}>
          <i className="ti ti-chevron-left" aria-hidden="true" />
        </button>
        <button type="button" className="rvbtn" disabled={view.week_start === thisWeek} onClick={() => onGoToWeek(thisWeek)}>{t("This week")}</button>
        <button type="button" className="rvbtn" aria-label={t("Next week")} disabled={isCurrentOrLater} onClick={() => onGoToWeek(addDays(view.week_start, 7))}>
          <i className="ti ti-chevron-right" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
