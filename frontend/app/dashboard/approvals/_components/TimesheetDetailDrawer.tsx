"use client";

// One submitted timesheet, read-only (the same grid the employee filled in), with its history and the approver's actions:
// Approve and Send back (a written reason is required and the employee sees it), and for HR, Reopen an approved sheet.
// Which buttons appear comes from the server (can_decide / can_unlock), never from guessing at permissions here.

import { useState } from "react";
import RejectReasonModal, { type RejectReasonWording } from "./RejectReasonModal";
import TimesheetProjects from "@/components/timesheet/TimesheetProjects";
import TimesheetHistory from "@/components/timesheet/TimesheetHistory";
import TimesheetStatusBadge from "@/components/timesheet/TimesheetStatusBadge";
import { useTimesheetDecision } from "@/hooks/useTimesheetDecision";
import { toGridLines, weekRangeLabel } from "@/lib/timesheet";

interface Props {
  timesheetId: string | null;
  onClose: () => void;
  /** The list behind the drawer should refetch: a decision changed what is waiting. */
  onChanged: () => void;
}

type Asking = "send_back" | "unlock" | null;

const NOOP = () => undefined;

const SEND_BACK: Partial<RejectReasonWording> = {
  title: "Send timesheet back", actionLabel: "Send back", busyLabel: "Sending…",
  requiredMessage: "Please give a reason for sending this timesheet back.",
};
const UNLOCK: Partial<RejectReasonWording> = {
  title: "Reopen timesheet", actionLabel: "Reopen timesheet", busyLabel: "Reopening…",
  requiredMessage: "Please give a reason for reopening this timesheet.",
};

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="ta-drawer-row">
      <span style={{ color: "var(--ta-text-muted)", fontSize: 13 }}>{label}</span>
      <span style={{ fontWeight: 600, fontSize: 13 }}>{value}</span>
    </div>
  );
}

export default function TimesheetDetailDrawer({ timesheetId, onClose, onChanged }: Props) {
  const { view, loading, error, isBusy, problem, clearProblem, approve, sendBack, unlock } = useTimesheetDecision(timesheetId, onChanged);
  const [asking, setAsking] = useState<Asking>(null);

  async function submitReason(reason: string) {
    const isDone = asking === "unlock" ? await unlock(reason) : await sendBack(reason);
    if (isDone) setAsking(null);
  }

  function ask(kind: Asking) {
    clearProblem();
    setAsking(kind);
  }

  return (
    <>
      <div className={`drawer-overlay ${timesheetId ? "open" : ""}`} onClick={onClose} />
      <div className={`drawer emp-drawer ${timesheetId ? "open" : ""}`} role="dialog" aria-label="Timesheet details">
        {timesheetId && (
          <>
            <div className="drawer-header">
              <div className="drawer-title">Timesheet</div>
              <button className="drawer-close" onClick={onClose} aria-label="Close"><i className="ti ti-x" /></button>
            </div>
            <div className="drawer-body">
              {loading && <p>Loading…</p>}
              {!loading && !view && <p role="alert">{error ?? "This timesheet could not be loaded."}</p>}
              {view && (
                <>
                  <div className="ta-drawer-section">
                    <div style={{ fontSize: 15, fontWeight: 700 }}>{view.employee?.name}</div>
                    <div style={{ fontSize: 12, color: "var(--ta-text-muted)", marginBottom: 10 }}>{view.employee?.employee_id}</div>
                    <TimesheetStatusBadge status={view.status} isLate={view.is_late} />
                  </div>
                  <div className="ta-drawer-section">
                    <Fact label="Week" value={weekRangeLabel(view.week_start, view.week_end)} />
                    <Fact label="Project hours" value={view.totals.week} />
                    <Fact label="Billable hours" value={view.totals.billable} />
                    <Fact label="Attendance hours (from punches)" value={view.totals.attendance_hours} />
                    {view.return_reason && <Fact label="Last reason" value={view.return_reason} />}
                  </div>
                  <div className="ta-drawer-section">
                    <TimesheetProjects
                      days={view.days} lines={toGridLines(view.lines)} limits={view.limits} isReadOnly
                      onHoursChange={NOOP} onNoteChange={NOOP} onBillableChange={NOOP}
                    />
                  </div>
                  <div className="ta-drawer-section">
                    <div className="ta-drawer-label">History</div>
                    <TimesheetHistory events={view.events} />
                  </div>
                  {problem && !asking && <p role="alert" style={{ color: "var(--error)" }}>{problem}</p>}
                </>
              )}
            </div>
            {view && (view.can_decide || view.can_unlock) && (
              <div className="drawer-footer">
                {view.can_unlock && (
                  <button className="ta-bulk-btn" style={{ padding: "9px 18px" }} disabled={isBusy} onClick={() => ask("unlock")}>
                    <i className="ti ti-lock-open" /> Reopen for correction
                  </button>
                )}
                {view.can_decide && (
                  <>
                    <button className="ta-bulk-btn ta-bulk-reject" style={{ padding: "9px 18px" }} disabled={isBusy} onClick={() => ask("send_back")}>
                      <i className="ti ti-arrow-back-up" /> Send back
                    </button>
                    <button className="ta-bulk-btn ta-bulk-approve" style={{ padding: "9px 18px" }} disabled={isBusy} onClick={approve}>
                      <i className="ti ti-check" /> {isBusy ? "Working…" : "Approve"}
                    </button>
                  </>
                )}
              </div>
            )}
          </>
        )}
      </div>
      {asking && view && (
        <RejectReasonModal
          employeeName={view.employee?.name ?? "employee"} isSaving={isBusy} serverError={problem}
          wording={asking === "unlock" ? UNLOCK : SEND_BACK} onSubmit={submitReason} onCancel={() => setAsking(null)}
        />
      )}
    </>
  );
}
