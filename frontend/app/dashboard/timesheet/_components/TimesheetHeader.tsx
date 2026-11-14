"use client";

import TimesheetStatusBadge from "@/components/timesheet/TimesheetStatusBadge";
import { addDays, currentMonday, weekRangeLabel } from "@/lib/timesheet";
import type { TimesheetWeekView } from "@/types/timesheet";

interface Props {
  view: TimesheetWeekView;
  onGoToWeek: (weekStart: string) => void;
}

function dueText(dueIso: string): string {
  return new Date(`${dueIso}T12:00:00`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
}

export default function TimesheetHeader({ view, onGoToWeek }: Props) {
  const thisWeek = currentMonday();
  const isCurrentOrLater = view.week_start >= thisWeek;
  return (
    <div className="ess-pagehead" style={{ alignItems: "center", flexWrap: "wrap", gap: 12 }}>
      <div>
        <h2 style={{ margin: 0 }}>{weekRangeLabel(view.week_start, view.week_end)}</h2>
        <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--muted)" }}>
          Due {dueText(view.due_date)}{view.approver ? ` · Approver: ${view.approver.name}` : ""}
        </p>
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <TimesheetStatusBadge status={view.status} isLate={view.is_late} />
        <button type="button" className="rvbtn" aria-label="Previous week" onClick={() => onGoToWeek(addDays(view.week_start, -7))}>
          <i className="ti ti-chevron-left" aria-hidden="true" />
        </button>
        <button type="button" className="rvbtn" disabled={view.week_start === thisWeek} onClick={() => onGoToWeek(thisWeek)}>This week</button>
        <button type="button" className="rvbtn" aria-label="Next week" disabled={isCurrentOrLater} onClick={() => onGoToWeek(addDays(view.week_start, 7))}>
          <i className="ti ti-chevron-right" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
