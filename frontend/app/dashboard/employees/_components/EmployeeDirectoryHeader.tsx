"use client";

import DraftsPopover from "./DraftsPopover";

interface Props {
  totalHeadcount: number;
  canCreate: boolean;
  exporting: boolean;
  onResumeDraft: (hireActionId: string) => void;
  onOpenAiAssist: () => void;
  onExport: () => void;
  onHireEmployee: () => void;
}

export default function EmployeeDirectoryHeader({
  totalHeadcount, canCreate, exporting, onResumeDraft, onOpenAiAssist, onExport, onHireEmployee,
}: Props) {
  return (
    <div className="pagehead">
      <div style={{ maxWidth: 560 }}>
        <h1>Employee <em>directory</em></h1>
        <p className="lede">
          Everyone on the payroll, and everyone on their way onto it. Hire a new employee, track
          onboarding, and see who is still missing the details that gate a payroll run.
        </p>
        <div style={{ display: "flex", gap: 10, marginTop: 14, flexWrap: "wrap" }}>
          <DraftsPopover onResume={onResumeDraft} />
          <button
            className="btn btn-ghost" style={{ display: "flex", alignItems: "center", gap: 6, position: "relative" }}
            onClick={onOpenAiAssist} suppressHydrationWarning
          >
            <i className="ti ti-sparkles" style={{ fontSize: 15 }} /> AI Assist
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--success)", position: "absolute", top: 4, right: 4 }} />
          </button>
          <button
            className="btn btn-ghost" style={{ display: "flex", alignItems: "center", gap: 6 }}
            onClick={onExport} disabled={exporting} suppressHydrationWarning
          >
            <i className={`ti ${exporting ? "ti-loader-2 animate-spin" : "ti-download"}`} style={{ fontSize: 15 }} />
            {exporting ? "Exporting…" : "Export"}
          </button>
          {canCreate && (
            <button onClick={onHireEmployee} suppressHydrationWarning
              className="btn btn-filled" style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <i className="ti ti-plus" style={{ fontSize: 15 }} />
              Hire employee
            </button>
          )}
        </div>
      </div>
      <div style={{ textAlign: "right", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, justifyContent: "flex-end", fontSize: 12, fontWeight: 600, color: "var(--success)" }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--success)" }} /> All changes saved
        </div>
        <div style={{ fontSize: 32, fontWeight: 800, color: "var(--on-bg)", marginTop: 4 }}>{totalHeadcount}</div>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.04em", color: "var(--on-variant)" }}>CURRENTLY EMPLOYED</div>
      </div>
    </div>
  );
}
