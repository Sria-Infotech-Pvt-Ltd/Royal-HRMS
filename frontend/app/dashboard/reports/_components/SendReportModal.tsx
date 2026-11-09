"use client";

import { useState } from "react";
import Modal from "@/components/Modal";
import { useRecipientSearch } from "@/hooks/useReports";
import { emailOmitsNotice } from "@/lib/reportQuery";
import type { ReportDefinition, ReportRecipient } from "@/types/reports";

interface SendReportModalProps {
  report: ReportDefinition;
  maxRecipients: number;
  maxNoteLength: number;
  isBusy: boolean;
  /** The server's message when sending failed; the chosen people and the note stay in place. */
  serverError: string;
  onSend: (recipientIds: string[], note: string) => void;
  onClose: () => void;
}

/** Email a report to chosen active employees. The server builds the file; nothing typed here becomes report content. */
export default function SendReportModal({ report, maxRecipients, maxNoteLength, isBusy, serverError, onSend, onClose }: SendReportModalProps) {
  const [term, setTerm] = useState("");
  const [chosen, setChosen] = useState<ReportRecipient[]>([]);
  const [note, setNote] = useState("");
  const [localError, setLocalError] = useState("");
  const { results, loading } = useRecipientSearch(term);

  const offered = results.filter(person => !chosen.some(picked => picked.id === person.id));
  const isFull = chosen.length >= maxRecipients;

  function add(person: ReportRecipient) {
    if (isFull) return;
    setChosen([...chosen, person]);
    setTerm("");
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (chosen.length === 0) { setLocalError("Choose at least one person to send this report to."); return; }
    setLocalError("");
    onSend(chosen.map(person => person.id), note.trim());
  }

  const message = localError || serverError;
  return (
    <Modal title={`Email: ${report.title}`} onClose={onClose} closeDisabled={isBusy}>
      <form onSubmit={submit} style={{ display: "grid", gap: 12 }}>
        <p style={{ margin: 0, fontSize: 13, color: "var(--on-variant)" }}>
          The report is attached as a CSV file, built from what you are allowed to see. Each person receives their own copy.
          {" "}{emailOmitsNotice(report)}
        </p>

        <label className="field-label" htmlFor="report-recipient">Send to (active employees, up to {maxRecipients})</label>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {chosen.map(person => (
            <span key={person.id} className="badge badge-info" style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
              {person.name} ({person.employee_id})
              <button type="button" aria-label={`Remove ${person.name}`} style={{ background: "none", border: 0, cursor: "pointer" }}
                onClick={() => setChosen(chosen.filter(picked => picked.id !== person.id))}>✕</button>
            </span>
          ))}
        </div>
        <input id="report-recipient" className="field-input" placeholder="Search by name or employee ID" value={term}
          onChange={event => setTerm(event.target.value)} disabled={isFull} autoComplete="off" />
        {term.trim().length >= 2 && (
          <div role="listbox" aria-label="Matching employees" style={{ border: "1px solid var(--line)", borderRadius: 8, maxHeight: 180, overflowY: "auto" }}>
            {loading && <div style={{ padding: 10, fontSize: 13 }}>Searching…</div>}
            {!loading && offered.length === 0 && <div style={{ padding: 10, fontSize: 13 }}>No matching active employees.</div>}
            {offered.map(person => (
              <button key={person.id} type="button" role="option" aria-selected="false" onClick={() => add(person)}
                style={{ display: "block", width: "100%", textAlign: "left", padding: "8px 10px", background: "none", border: 0, cursor: "pointer" }}>
                <strong>{person.name}</strong> <span style={{ color: "var(--on-variant)", fontSize: 12 }}>{person.employee_id}{person.designation ? ` · ${person.designation}` : ""}</span>
              </button>
            ))}
          </div>
        )}

        <label className="field-label" htmlFor="report-note">Note (optional)</label>
        <textarea id="report-note" className="field-input" rows={3} maxLength={maxNoteLength} value={note} onChange={event => setNote(event.target.value)} />

        {message && <p role="alert" style={{ color: "var(--error)", margin: 0 }}>{message}</p>}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={isBusy}>Cancel</button>
          <button type="submit" className="btn btn-filled" disabled={isBusy}>{isBusy ? "Sending…" : "Send report"}</button>
        </div>
      </form>
    </Modal>
  );
}
