"use client";

import DraftsPopover from "./DraftsPopover";

interface Props {
  totalHeadcount: number;
  canCreate: boolean;
  /** employees.edit — the artifact reserves AI Assist for the HR persona. */
  canUseAiAssist: boolean;
  /** employees.export — Payroll Admin and HR have it; a Reporting Manager does not. */
  canExport: boolean;
  exporting: boolean;
  onResumeDraft: (hireActionId: string) => void;
  onOpenAiAssist: () => void;
  onExport: () => void;
  onHireEmployee: () => void;
}

export default function EmployeeDirectoryHeader({
  totalHeadcount, canCreate, canUseAiAssist, canExport, exporting, onResumeDraft, onOpenAiAssist, onExport, onHireEmployee,
}: Props) {
  return (
    <div className="pagehead">
      <div style={{ minWidth: 0, flex: "1 1 0" }}>
        <h1>Employee <em className="hl">directory</em></h1>
        <p className="lede">
          Everyone on the payroll, and everyone on their way onto it. Hire a new employee, track
          onboarding, and see who is still missing the details that gate a payroll run.
        </p>
        <div className="headacts" style={{ gap: 10 }}>
          {canCreate && <DraftsPopover onResume={onResumeDraft} />}
          {canUseAiAssist && (
            <button
              className="btn btn-ghost" style={{ display: "flex", alignItems: "center", gap: 6, position: "relative" }}
              onClick={onOpenAiAssist} suppressHydrationWarning
            >
              <i className="ti ti-sparkles" style={{ fontSize: 15 }} /> AI Assist
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--success)", position: "absolute", top: 4, right: 4 }} />
            </button>
          )}
          {canExport && (
            <button
              className="btn btn-ghost" style={{ display: "flex", alignItems: "center", gap: 6 }}
              onClick={onExport} disabled={exporting} suppressHydrationWarning
            >
              <i className={`ti ${exporting ? "ti-loader-2 animate-spin" : "ti-download"}`} style={{ fontSize: 15 }} />
              {exporting ? "Exporting…" : "Export"}
            </button>
          )}
          {canCreate && (
            <button onClick={onHireEmployee} suppressHydrationWarning
              className="btn btn-filled" style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <i className="ti ti-plus" style={{ fontSize: 15 }} />
              Hire employee
            </button>
          )}
        </div>
      </div>
      <div className="bignum" style={{ flexShrink: 0 }}>
        <div className="saved" style={{ gap: 6, fontSize: 12, color: "var(--success)" }}>
          <i style={{ width: 6, height: 6, background: "var(--success)" }} /> All changes saved
        </div>
        <div className="n" style={{ fontWeight: 800, color: "var(--on-bg)" }}>{totalHeadcount}</div>
        <div className="l" style={{ fontSize: 11, letterSpacing: "0.04em", color: "var(--on-variant)" }}>CURRENTLY EMPLOYED</div>
      </div>
    </div>
  );
}
