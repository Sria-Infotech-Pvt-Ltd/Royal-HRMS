"use client";

import { useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

interface ImportResult {
  created:  number;
  updated:  number;
  failed:   number;
  errors:   { row: number; message: string }[];
}

interface Props {
  onClose:   () => void;
  onSuccess: () => void;
}

export default function BulkImportModal({ onClose, onSuccess }: Props) {
  const inputRef                  = useRef<HTMLInputElement>(null);
  const [file,       setFile]     = useState<File | null>(null);
  const [uploading,  setUploading] = useState(false);
  const [result,     setResult]   = useState<ImportResult | null>(null);
  const [error,      setError]    = useState<string | null>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = e.target.files?.[0] ?? null;
    setFile(picked);
    setResult(null);
    setError(null);
  }

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setError(null);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file, file.name);
      const res = await clientApi.post(API.employees.bulkImport, fd);
      const data: ImportResult = res.data?.data ?? res.data;
      setResult(data);
      if ((data.created + data.updated) > 0) onSuccess();
    } catch (err: unknown) {
      setError((err as { message?: string })?.message ?? "Import failed. Please check your file and try again.");
    } finally {
      setUploading(false);
    }
  }

  const isExcel = file && (file.name.endsWith(".xlsx") || file.name.endsWith(".xls") || file.name.endsWith(".csv"));

  return (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 520 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title"><i className="ti ti-file-upload" style={{ marginRight: 8 }} />Bulk Import Employees</div>
          <button className="modal-close" onClick={onClose}><i className="ti ti-x" /></button>
        </div>

        <div className="modal-body">
          {/* Instructions */}
          <div style={{ padding: "12px 14px", borderRadius: 8, background: "rgba(30,78,140,0.06)", border: "1px solid rgba(30,78,140,0.15)", marginBottom: 20, fontSize: 12, color: "var(--on-variant)", lineHeight: 1.6 }}>
            <div style={{ fontWeight: 600, color: "var(--primary)", marginBottom: 4, fontSize: 12 }}>
              <i className="ti ti-info-circle" style={{ marginRight: 5 }} />File Requirements
            </div>
            <ul style={{ margin: 0, paddingLeft: 16 }}>
              <li>Accepted formats: <strong>.xlsx</strong>, <strong>.xls</strong>, <strong>.csv</strong></li>
              <li>Required columns: <code style={{ background: "rgba(0,0,0,0.06)", padding: "0 4px", borderRadius: 3 }}>first_name</code>, <code style={{ background: "rgba(0,0,0,0.06)", padding: "0 4px", borderRadius: 3 }}>last_name</code>, <code style={{ background: "rgba(0,0,0,0.06)", padding: "0 4px", borderRadius: 3 }}>email</code>, <code style={{ background: "rgba(0,0,0,0.06)", padding: "0 4px", borderRadius: 3 }}>department</code>, <code style={{ background: "rgba(0,0,0,0.06)", padding: "0 4px", borderRadius: 3 }}>designation</code></li>
              <li>Maximum 500 rows per import</li>
            </ul>
          </div>

          {/* Drop zone */}
          <div
            onClick={() => inputRef.current?.click()}
            style={{
              border: `2px dashed ${file ? "var(--primary)" : "var(--outline-v)"}`,
              borderRadius: 10, padding: "28px 20px", textAlign: "center",
              cursor: "pointer", background: file ? "rgba(30,78,140,0.04)" : "var(--bg-low)",
              transition: "border-color 0.15s, background 0.15s", marginBottom: 16,
            }}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".xlsx,.xls,.csv"
              style={{ display: "none" }}
              onChange={handleFileChange}
            />
            <i className={`ti ${file ? "ti-file-check" : "ti-upload"}`} style={{ fontSize: 28, color: file ? "var(--primary)" : "var(--outline)", display: "block", marginBottom: 8 }} />
            {file ? (
              <>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--primary)" }}>{file.name}</div>
                <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 3 }}>
                  {(file.size / 1024).toFixed(1)} KB · Click to change
                </div>
              </>
            ) : (
              <>
                <div style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>Click to select file</div>
                <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 3 }}>.xlsx · .xls · .csv</div>
              </>
            )}
          </div>

          {file && !isExcel && (
            <div className="alert alert-error" style={{ marginBottom: 12 }}>
              <i className="ti ti-alert-circle" />
              <span>Unsupported file type. Please upload a .xlsx, .xls, or .csv file.</span>
            </div>
          )}

          {error && (
            <div className="alert alert-error" style={{ marginBottom: 12 }}>
              <i className="ti ti-alert-circle" />
              <span>{error}</span>
            </div>
          )}

          {/* Result summary */}
          {result && (
            <div style={{ borderRadius: 8, border: "1px solid var(--outline-v)", overflow: "hidden" }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", textAlign: "center" }}>
                {[
                  { label: "Created",  value: result.created, color: "var(--success)" },
                  { label: "Updated",  value: result.updated, color: "var(--primary)" },
                  { label: "Failed",   value: result.failed,  color: result.failed > 0 ? "var(--error)" : "var(--on-variant)" },
                ].map(({ label, value, color }) => (
                  <div key={label} style={{ padding: "12px 8px", borderRight: "1px solid var(--outline-v)" }}>
                    <div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div>
                    <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 2 }}>{label}</div>
                  </div>
                ))}
              </div>

              {result.errors.length > 0 && (
                <div style={{ borderTop: "1px solid var(--outline-v)", maxHeight: 140, overflowY: "auto" }}>
                  {result.errors.map((e, i) => (
                    <div key={i} style={{ display: "flex", gap: 8, padding: "7px 14px", borderBottom: "1px solid var(--outline-v)", fontSize: 12 }}>
                      <span style={{ color: "var(--on-variant)", flexShrink: 0 }}>Row {e.row}</span>
                      <span style={{ color: "var(--error)" }}>{e.message}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>
            {result ? "Close" : "Cancel"}
          </button>
          {!result && (
            <button
              className="btn btn-filled"
              onClick={handleUpload}
              disabled={!file || !isExcel || uploading}
              suppressHydrationWarning
            >
              {uploading
                ? <><i className="ti ti-loader-2 spin" /> Importing…</>
                : <><i className="ti ti-file-upload" /> Import</>
              }
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
