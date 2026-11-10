"use client";

import { useRef } from "react";
import Modal from "@/components/Modal";
import ImportJobPanel from "@/components/employees/ImportJobPanel";
import ImportPreviewTable, { ImportSummaryTiles } from "@/components/employees/ImportPreviewTable";
import ImportRecentJobs from "@/components/employees/ImportRecentJobs";
import { useEmployeeImport } from "@/hooks/useEmployeeImport";

interface Props {
  onClose: () => void;
  onSuccess: () => void;
}

const NOTE_STYLE = { fontSize: 12, color: "var(--on-variant)", lineHeight: 1.6 } as const;

export default function EmployeeImportModal({ onClose, onSuccess }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const flow = useEmployeeImport(onSuccess);
  const { step, file, preview, job, recent, error, isBusy, isActing } = flow;

  const footer = (
    <>
      <button className="btn btn-ghost" onClick={onClose}>{step === "job" ? "Close" : "Cancel"}</button>
      {step === "job" && job && !job.is_active && (
        <button className="btn btn-filled" onClick={flow.startNew} suppressHydrationWarning><i className="ti ti-plus" /> Import another file</button>
      )}
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
            {isBusy ? <><i className="ti ti-loader-2 spin" /> Starting…</> : <><i className="ti ti-check" /> Confirm import of {preview.summary.total}</>}
          </button>
        </>
      )}
    </>
  );

  return (
    <Modal title={<><i className="ti ti-file-upload" style={{ marginRight: 8 }} />Import Employees from Excel</>} onClose={onClose} maxWidth={860} footer={footer}>
      {step !== "job" && (
        <div style={{ ...NOTE_STYLE, marginBottom: 14 }}>
          <strong>1.</strong> Download the template and fill it in. <strong>2.</strong> Upload it and review the preview — nothing is created yet.{" "}
          <strong>3.</strong> Confirm. Every row must be valid to start. The employees are then created in the background, so you can close this window and come back: progress is saved. Each new employee then gets an activation email.
          <div style={{ marginTop: 8 }}>
            <button className="btn btn-ghost btn-sm" onClick={flow.downloadTemplate} suppressHydrationWarning>
              <i className="ti ti-download" /> Download template (.xlsx)
            </button>
          </div>
        </div>
      )}

      {step !== "job" && (
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

      {step === "job" && job && (
        <ImportJobPanel job={job} isActing={isActing} onCancel={flow.cancelJob} onRetryEmails={flow.retryEmails} onDownloadErrors={flow.downloadJobErrors} />
      )}

      {step === "start" && <ImportRecentJobs jobs={recent} onOpen={flow.openJob} />}
    </Modal>
  );
}
