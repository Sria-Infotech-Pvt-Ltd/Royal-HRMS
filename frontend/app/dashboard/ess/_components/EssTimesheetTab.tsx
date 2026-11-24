"use client";

// My Workspace > Attendance > Weekly timesheet. It opens inside the workspace (same banner and tab bar, Attendance stays
// selected) instead of on a page of its own. Pick a week, enter hours per project, save a draft or submit for approval.

import { useTimesheetWeek } from "@/hooks/useTimesheetWeek";
import { useT } from "@/hooks/useI18n";
import TimesheetEditor from "../../timesheet/_components/TimesheetEditor";
import TimesheetHeader from "../../timesheet/_components/TimesheetHeader";

interface Props {
  /** The Monday of the week being shown (YYYY-MM-DD). */
  week: string;
  /** An admin looking at someone else's workspace: the sheet is shown, nothing can be changed. */
  isReadOnly: boolean;
  onGoToWeek: (weekStart: string) => void;
  onBack: () => void;
}

export default function EssTimesheetTab({ week, isReadOnly, onGoToWeek, onBack }: Props) {
  const t = useT();
  const { view, loading, error, refetch, save, submit, isSaving, isSubmitting, problems } = useTimesheetWeek(week);

  return (
    <div className="ess-card">
      <button type="button" className="rvbtn ghost" style={{ marginBottom: 8 }} onClick={onBack}>
        <i className="ti ti-arrow-left" aria-hidden="true" /> {t("Back to Attendance")}
      </button>
      {loading && <p>{t("Loading…")}</p>}
      {!loading && !view && (
        <div role="alert">
          <p>{error ?? t("The timesheet could not be loaded.")}</p>
          <button type="button" className="rvbtn" onClick={refetch}>{t("Try again")}</button>
        </div>
      )}
      {view && (
        <>
          <TimesheetHeader view={view} onGoToWeek={onGoToWeek} />
          <TimesheetEditor
            key={`${view.week_start}|${view.status}|${view.totals.week}|${view.events.length}|${view.lines.length}`}
            view={view} isReadOnly={isReadOnly} isSaving={isSaving} isSubmitting={isSubmitting} problems={problems}
            onSave={save} onSubmit={submit}
          />
        </>
      )}
    </div>
  );
}
