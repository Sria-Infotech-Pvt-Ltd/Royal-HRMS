"use client";

// The Before → After / Approval & reversibility / "not changed" sections shared by every action type, laid out
// as the reference's cards. The "delimited to … the new record runs …" sentence lives in the dialog footer.

import type { Employee } from "../../_data";
import type { ActionType, FieldDiffRow } from "./types";

interface DetailsProps {
  employee: Employee;
  rows: { label: string; value: string }[];
}

/** "Employee details — not changed by this action": shown from the start, before any action is chosen. */
export function EmployeeDetailsCard({ employee, rows }: DetailsProps) {
  return (
    <>
      <div className="divider" />
      <div className="sechead">EMPLOYEE DETAILS — NOT CHANGED BY THIS ACTION</div>
      <div className="rvcard">
        <div className="kvlist">
          <div className="kv"><span>Employee</span><b>{employee.firstName} {employee.lastName} · {employee.code}</b></div>
          {rows.map(row => <div className="kv" key={row.label}><span>{row.label}</span><b>{row.value}</b></div>)}
        </div>
      </div>
    </>
  );
}

interface Props extends DetailsProps {
  actionType: ActionType;
  diffRows: FieldDiffRow[];
  route: string;
  effectiveFromLabel: string;
  raisedByName: string;
  raisedByRole: string;
  reversibility: { text: string; tone: "purple" | "amber" };
  separationConfirmed: boolean;
  setSeparationConfirmed: (value: boolean) => void;
  /** True when submitting raises a request that waits for approval instead of applying instantly. */
  requiresApproval?: boolean;
}

export default function ActionSummarySections({
  employee, rows, actionType, diffRows, route, effectiveFromLabel, raisedByName, raisedByRole,
  reversibility, separationConfirmed, setSeparationConfirmed, requiresApproval = false,
}: Props) {
  const status = actionType === "separation"
    ? "Pending approval — a real multi-stage approval chain runs on this request."
    : requiresApproval
      ? "Pending approval — nothing changes until every approver on the route has approved."
      : "Applied immediately — no pending-approval queue exists for this action yet.";

  return (
    <>
      <div className="divider" />
      <div className="sechead">BEFORE → AFTER</div>
      <div className="rvcard">
        <div className="kvlist">
          {diffRows.map(row => (
            <div className="kv" key={row.key}>
              <span>{row.label}</span>
              {row.after === null
                ? <b style={{ fontWeight: 500, color: "var(--muted)" }}>unchanged</b>
                : <b style={actionType === "separation" ? { color: "var(--warn)" } : undefined}>{row.before} → {row.after}</b>}
            </div>
          ))}
        </div>
      </div>

      <div className="divider" />
      <div className="sechead">APPROVAL &amp; REVERSIBILITY</div>
      <div className="rvcard">
        <div className="kvlist">
          <div className="kv"><span>Approval route</span><b>{route}</b></div>
          <div className="kv"><span>Status on apply</span><b>{status}</b></div>
          <div className="kv"><span>Effective date</span><b>{effectiveFromLabel}</b></div>
          <div className="kv"><span>Raised by</span><b>{raisedByName} · {raisedByRole}</b></div>
        </div>
      </div>
      <div className={`note ${reversibility.tone === "amber" ? "warn" : "info"}`}><b>Reversibility</b>{reversibility.text}</div>

      {actionType === "separation" && (
        <div className="note warn">
          <div>
            <b>This cannot be undone</b>
            Recording a separation ends the current record and starts the exit process. It cannot be reversed — a
            returning employee needs a fresh Hire action.
            <label className="chkline" style={{ marginTop: 8 }}>
              <input type="checkbox" checked={separationConfirmed} onChange={event => setSeparationConfirmed(event.target.checked)} />
              <span>I have verified these values and I am authorised to apply this separation.</span>
            </label>
          </div>
        </div>
      )}

      <EmployeeDetailsCard employee={employee} rows={rows} />
    </>
  );
}
