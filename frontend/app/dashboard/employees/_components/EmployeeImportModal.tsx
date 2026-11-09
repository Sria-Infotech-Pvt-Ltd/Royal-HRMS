"use client";

import { useRef } from "react";
import Modal from "@/components/Modal";
import ImportPreviewTable, { ImportSummaryTiles } from "@/components/employees/ImportPreviewTable";
import { useEmployeeImport } from "@/hooks/useEmployeeImport";
import { describeCommitResult } from "@/lib/employeeImport";

interface Props {
  onClose: () => void;
  onSuccess: () => void;
}

const NOTE_STYLE = { fontSize: 12, color: "var(--on-variant)", lineHeight: 1.6 } as const;

export default function EmployeeImportModal({ onClose, onSuccess }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const flow = useEmployeeImport(onSuccess);
  const { step, file, preview, result, progress, error, isBusy } = flow;

  const footer = (
    <>
      <button className="btn btn-ghost" onClick={onClose}>{step === "done" ? "Close" : "Cancel"}</button>
      {step === "start" && (
        <button className="btn btn-filled" onClick={flow.runPreview} disabled={isBusy || !file} suppressHydrationWarning>
          {isBusy ? <><i className="ti ti-loader-2 spin" /> Checking…</> : <><i className="ti ti-eye" /> Preview</>}
        </button>
      )}
      {step === "previewed" && preview && (
        <>
          {!preview.can_import && (
            <button className="btn btn-ghost" onClick={flow.downloadErrors} suppressHydrationWarning>
              <i className="ti ti-download" /> Download errors (Excel)
            </button>
          )}
          <button className="btn btn-filled" onClick={flow.confirmImport} disabled={isBusy || !preview.can_import} suppressHydrationWarning>
            {isBusy ? <><i className="ti ti-loader-2 spin" /> Importing…</> : <><i className="ti ti-check" /> Confirm import of {preview.summary.total}</>}
          </button>
        </>
      )}
    </>
  );

  return (
    <Modal title={<><i className="ti ti-file-upload" style={{ marginRight: 8 }} />Import Employees from Excel</>} onClose={onClose} maxWidth={860} footer={footer}>
      {step !== "done" && (
        <div style={{ ...NOTE_STYLE, marginBottom: 14 }}>
          <strong>1.</strong> Download the template and fill it in. <strong>2.</strong> Upload it and review the preview — nothing is created yet.{" "}
          <strong>3.</strong> Confirm. If any row has an error, nobody is imported. Each new employee then gets an activation email.
          <div style={{ marginTop: 8 }}>
            <button className="btn btn-ghost btn-sm" onClick={flow.downloadTemplate} suppressHydrationWarning>
              <i className="ti ti-download" /> Download template (.xlsx)
            </button>
          </div>
        </div>
      )}

      {step !== "done" && (
        <div onClick={() => inputRef.current?.click()} style={{ border: `2px dashed ${file ? "var(--primary)" : "var(--outline-v)"}`, borderRadius: 10, padding: "20px", textAlign: "center", cursor: "pointer", background: "var(--bg-low)", marginBottom: 14 }}>
          <input ref={inputRef} type="file" accept=".xlsx" style={{ display: "none" }} onChange={event => flow.chooseFile(event.target.files?.[0] ?? null)} />
          <i className={`ti ${file ? "ti-file-check" : "ti-upload"}`} style={{ fontSize: 26, display: "block", marginBottom: 6 }} />
          <div style={{ fontSize: 13, fontWeight: 600 }}>{file ? file.name : "Click to choose the filled .xlsx file"}</div>
        </div>
      )}

      {error && <div className="alert alert-error" style={{ marginBottom: 12 }}><i className="ti ti-alert-circle" /><span>{error}</span></div>}

      {step === "previewed" && preview && (
        <>
          <ImportSummaryTiles summary={preview.summary} />
          <div style={{ ...NOTE_STYLE, marginBottom: 8 }}>
            You can import into: <strong>{preview.allowed_branches.join(", ") || "no branch"}</strong>.{" "}
            {preview.can_import ? "Everything is valid. Press Confirm to create these employees." : "Fix the rows below (or download the error file), then upload again. Nothing has been created."}
          </div>
          <ImportPreviewTable rows={preview.rows} />
        </>
      )}

      {step === "done" && result && (
        <div>
          <div className="alert" style={{ marginBottom: 12 }}><i className="ti ti-circle-check" /><span>{describeCommitResult(result, progress)}</span></div>
          {(progress?.failed ?? result.invite_failures).length > 0 && (
            <div style={{ border: "1px solid var(--outline-v)", borderRadius: 8, padding: 10 }}>
              <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 6 }}>Activation emails not sent (employees were created)</div>
              {(progress?.failed ?? result.invite_failures).map(failure => (
                <div key={failure.employee_id} style={NOTE_STYLE}>Row {failure.row}: employee {failure.employee_id} — {failure.reason}</div>
              ))}
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}
