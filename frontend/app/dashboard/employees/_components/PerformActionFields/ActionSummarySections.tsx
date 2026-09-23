"use client";

// The Before → After / Approval & reversibility / not-changed / footer-note
// sections shared by every action type — split out of PerformActionModal
// purely to keep that file under the file-length guideline.

import type { Employee } from "../../_data";
import type { ActionType, FieldDiffRow } from "./types";

interface Props {
  employee: Employee;
  actionType: ActionType;
  diffRows: FieldDiffRow[];
  notChangedRows: { label: string; value: string }[];
  route: string;
  effectiveFromLabel: string;
  raisedByName: string;
  raisedByRole: string;
  reversibility: { text: string; tone: "purple" | "amber" };
  separationConfirmed: boolean;
  setSeparationConfirmed: (v: boolean) => void;
  delimitedToLabel: string;
  newRecordFromLabel: string;
}

export default function ActionSummarySections({
  employee, actionType, diffRows, notChangedRows, route, effectiveFromLabel,
  raisedByName, raisedByRole, reversibility, separationConfirmed, setSeparationConfirmed,
  delimitedToLabel, newRecordFromLabel,
}: Props) {
  return (
    <>
      <div className="section-label">Before → After</div>
      <div className="rounded-lg p-3.5 space-y-1.5" style={{ background: "var(--sunken)" }}>
        {diffRows.map(row => (
          <div key={row.key} className="flex justify-between text-[12.5px]">
            <span style={{ color: "var(--muted)" }}>{row.label}</span>
            {row.after === null ? (
              <span style={{ color: "var(--muted)" }}>unchanged</span>
            ) : (
              <span className="font-semibold" style={{ color: actionType === "separation" ? "var(--warn)" : "var(--on-bg)" }}>
                {row.before} <i className="ti ti-arrow-right" style={{ margin: "0 4px" }} /> {row.after}
              </span>
            )}
          </div>
        ))}
      </div>

      <div className="section-label">Approval &amp; reversibility</div>
      <div className="rounded-lg p-3.5 space-y-1.5" style={{ background: "rgba(124,58,237,0.06)", border: "1px solid rgba(124,58,237,0.18)" }}>
        <div className="text-[12.5px]"><strong>Approval route:</strong> {route}</div>
        <div className="text-[12.5px]">
          <strong>Status on apply:</strong>{" "}
          {actionType === "separation"
            ? "Pending approval — a real multi-stage approval chain runs on this request."
            : "Applied immediately — no pending-approval queue exists for this action yet."}
        </div>
        <div className="text-[12.5px]"><strong>Effective date:</strong> {effectiveFromLabel}</div>
        <div className="text-[12.5px]"><strong>Raised by:</strong> {raisedByName} ({raisedByRole})</div>
      </div>

      <div
        className="rounded-lg p-3 text-[12.5px] font-medium"
        style={reversibility.tone === "amber"
          ? { background: "var(--warn-c)", color: "var(--warn)" }
          : { background: "rgba(124,58,237,0.10)", color: "var(--primary)" }}
      >
        {reversibility.text}
      </div>

      {actionType === "separation" && (
        <>
          <div className="rounded-lg p-3 text-[12.5px] font-medium" style={{ background: "var(--warn-c)", color: "var(--warn)" }}>
            This cannot be undone: recording a separation ends the current record and starts the exit process.
            It cannot be reversed — a returning employee needs a fresh Hire action.
          </div>
          <label className="flex items-start gap-2 text-[13px]">
            <input type="checkbox" className="mt-0.5" checked={separationConfirmed} onChange={e => setSeparationConfirmed(e.target.checked)} />
            I have verified these values and I am authorised to apply this separation.
          </label>
        </>
      )}

      <div className="section-label">Employee details — not changed by this action</div>
      <div className="rounded-lg p-3.5 space-y-1.5" style={{ background: "var(--sunken)" }}>
        <div className="flex justify-between text-[12.5px]">
          <span style={{ color: "var(--muted)" }}>Employee</span>
          <span className="font-semibold">{employee.firstName} {employee.lastName} · {employee.code}</span>
        </div>
        {notChangedRows.map(r => (
          <div key={r.label} className="flex justify-between text-[12.5px]">
            <span style={{ color: "var(--muted)" }}>{r.label}</span>
            <span className="font-semibold">{r.value}</span>
          </div>
        ))}
      </div>

      <p className="hint">
        Current record will be delimited to {delimitedToLabel}; the new record runs {newRecordFromLabel} → 31-12-9999.
      </p>
    </>
  );
}
