"use client";

// Real "Weekly timesheet" card — hours logged this week come from actual
// AttendanceRecord sums (useWeeklyTimesheet -> /attendance/my-weekly-timesheet/),
// and "Submit timesheet" persists a real WeeklyTimesheetSubmission row, not a
// no-op button. Shared between the ESS Home ("Today" panel row) and
// Attendance tab (full card) — see the `compact` prop.

import { useWeeklyTimesheet } from "@/hooks/useWeeklyTimesheet";

function weekEndingLabel(weekEndIso: string): string {
  return new Date(weekEndIso + "T12:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "long" });
}

function dueDayLabel(weekStartIso: string): string {
  const start = new Date(weekStartIso + "T12:00:00");
  const friday = new Date(start);
  friday.setDate(start.getDate() + 4);
  return friday.toLocaleDateString("en-US", { weekday: "short" }).toUpperCase();
}

export default function WeeklyTimesheetCard({ compact = false }: { compact?: boolean }) {
  const { data, submitting, submit } = useWeeklyTimesheet();
  if (!data) return null;

  const remaining = Math.max(0, data.target_hours - data.hours_logged);

  if (compact) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 0", borderBottom: "1px solid var(--outline-v)" }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--on-bg)" }}>Weekly timesheet</div>
          <div style={{ fontSize: 11.5, color: "var(--on-variant)" }}>{data.hours_logged} of {data.target_hours} hours logged</div>
        </div>
        <span className={`badge ${data.submitted ? "badge-success" : "badge-warn"}`}>
          {data.submitted ? "SUBMITTED" : `DUE ${dueDayLabel(data.week_start)}`}
        </span>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="page-header" style={{ padding: "18px 20px 4px" }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 15 }}>Weekly timesheet</div>
          <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 2 }}>
            {data.hours_logged} of {data.target_hours} hours logged for the current demo week.
          </div>
        </div>
        <button className="btn btn-filled btn-sm" onClick={submit} disabled={submitting || data.submitted}>
          {data.submitted ? "Submitted" : submitting ? "Submitting…" : "Submit timesheet"}
        </button>
      </div>
      <div style={{ padding: "8px 20px 20px" }}>
        <div style={{ fontWeight: 600, fontSize: 13, color: "var(--on-bg)" }}>Week ending {weekEndingLabel(data.week_end)}</div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 4 }}>
          <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
            {data.submitted
              ? `Submitted on ${data.submitted_at ? new Date(data.submitted_at).toLocaleDateString("en-GB") : "—"}.`
              : remaining > 0
                ? `${remaining} hour${remaining === 1 ? "" : "s"} remaining · Submit after completing your work summary.`
                : "Target reached — ready to submit."}
          </div>
          {!data.submitted && <span className="badge badge-warn">DUE {dueDayLabel(data.week_start)}</span>}
        </div>
      </div>
    </div>
  );
}
