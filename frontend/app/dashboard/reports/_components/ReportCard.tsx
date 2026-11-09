"use client";

import { useMemo, useState } from "react";
import { useToast } from "@/components/ToastProvider";
import { useReportActions, useReportPreview } from "@/hooks/useReports";
import { defaultFilters } from "@/lib/reportQuery";
import type { ReportCatalog, ReportDefinition, ReportFilterValues } from "@/types/reports";
import SendReportModal from "./SendReportModal";

interface ReportCardProps {
  report: ReportDefinition;
  limits: ReportCatalog["limits"];
}

/** One report: its filters, a preview of the first rows, a download, and an email to chosen colleagues. */
export default function ReportCard({ report, limits }: ReportCardProps) {
  const { showToast } = useToast();
  const [filters, setFilters] = useState<ReportFilterValues>(() => defaultFilters(report));
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const stable = useMemo(() => filters, [filters]);
  const preview = useReportPreview(report.key, stable, isPreviewing);
  const actions = useReportActions(report.key, stable);

  async function handleDownload() {
    if (await actions.download()) showToast(`${report.title} downloaded.`, "success");
  }

  async function handleSend(recipientIds: string[], note: string) {
    const message = await actions.send(recipientIds, note);
    if (message) {
      setIsSending(false);
      showToast(message, "success");
    }
  }

  return (
    <section className="card" style={{ padding: 18, display: "grid", gap: 12 }}>
      <div>
        <h2 style={{ margin: 0, fontSize: 16 }}>{report.title}</h2>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--on-variant)" }}>{report.description}</p>
      </div>

      {report.filters.length > 0 && (
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {report.filters.map(filter => (
            <label key={filter.key} style={{ display: "grid", gap: 4, fontSize: 12 }}>
              {filter.label}
              {filter.kind === "date" ? (
                <input type="date" className="field-input" value={filters[filter.key] ?? ""}
                  onChange={event => setFilters({ ...filters, [filter.key]: event.target.value })} />
              ) : (
                <select className="field-input field-select" value={filters[filter.key] ?? ""}
                  onChange={event => setFilters({ ...filters, [filter.key]: event.target.value })}>
                  {filter.options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              )}
            </label>
          ))}
        </div>
      )}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button type="button" className="btn btn-filled btn-sm" onClick={handleDownload} disabled={actions.isBusy}>
          <i className="ti ti-download" /> Download CSV
        </button>
        <button type="button" className="btn btn-outline btn-sm" onClick={() => { actions.clearError(); setIsSending(true); }}>
          <i className="ti ti-mail-forward" /> Email report
        </button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setIsPreviewing(!isPreviewing)}>
          <i className="ti ti-eye" /> {isPreviewing ? "Hide preview" : "Preview"}
        </button>
      </div>
      {actions.error && !isSending && <p role="alert" style={{ color: "var(--error)", margin: 0, fontSize: 13 }}>{actions.error}</p>}

      {isPreviewing && (
        <div style={{ overflowX: "auto" }}>
          {preview.loading && <p style={{ fontSize: 13 }}>Loading…</p>}
          {preview.error && <p role="alert" style={{ color: "var(--error)", fontSize: 13 }}>{preview.error}</p>}
          {preview.data && (
            <>
              <p style={{ fontSize: 12, color: "var(--on-variant)", margin: "0 0 6px" }}>
                {preview.data.row_count} row{preview.data.row_count === 1 ? "" : "s"} · showing the first {preview.data.rows.length}
              </p>
              <table className="data-table" style={{ minWidth: 480 }}>
                <thead><tr>{preview.data.headers.map(header => <th key={header}>{header}</th>)}</tr></thead>
                <tbody>
                  {preview.data.rows.length === 0 && <tr><td colSpan={preview.data.headers.length || 1}>No rows for these filters.</td></tr>}
                  {preview.data.rows.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>)}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}

      {isSending && (
        <SendReportModal
          report={report} maxRecipients={limits.max_recipients} maxNoteLength={limits.max_note_length}
          isBusy={actions.isBusy} serverError={actions.error} onSend={handleSend} onClose={() => setIsSending(false)}
        />
      )}
    </section>
  );
}
