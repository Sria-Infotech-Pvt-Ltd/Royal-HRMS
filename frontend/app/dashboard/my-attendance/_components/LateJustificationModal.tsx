"use client";

// Explain a late arrival (new) or resubmit one a reviewer sent back.
// Medical needs proof (PDF / JPG / PNG, 5 MB); the server checks the file's
// real content too. Punch times are never changed by this request.

import { useState } from "react";
import Modal from "@/components/Modal";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import {
  EXPLANATION_MAX, LATE_REASONS, PROOF_ACCEPT, lateFormErrors, type LateFormErrors,
} from "@/lib/lateJustification";
import type { LateJustificationRow, LateReason } from "@/types/lateJustification";

type Props = {
  onClose: () => void;
  onSuccess: (message: string) => void;
} & ({ mode: "new"; date: string; clockIn?: string | null } | { mode: "resubmit"; request: LateJustificationRow });

function fmtDate(iso: string) {
  return new Date(iso + "T12:00:00").toLocaleDateString("en-IN", { weekday: "short", day: "2-digit", month: "short", year: "numeric" });
}

export default function LateJustificationModal(props: Props) {
  const existing = props.mode === "resubmit" ? props.request : null;
  const date = existing ? existing.date : (props as { date: string }).date;
  const [reason, setReason] = useState<LateReason>(existing?.reason ?? "medical");
  const [explanation, setExplanation] = useState(existing?.explanation ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [errors, setErrors] = useState<LateFormErrors>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    const found = lateFormErrors(reason, explanation, file, !!existing?.has_document);
    setErrors(found);
    if (Object.keys(found).length) { setMsg("Please correct the highlighted fields."); return; }
    const fd = new FormData();
    fd.append("reason", reason);
    fd.append("explanation", explanation.trim());
    if (file) fd.append("document", file);
    if (!existing) fd.append("date", date);
    setBusy(true);
    setMsg(null);
    try {
      const { data } = await clientApi.post(
        existing ? API.attendance.lateJustificationResubmit(existing.id) : API.attendance.lateJustification, fd);
      props.onSuccess((data as { message?: string })?.message ?? "Submitted.");
      props.onClose();
    } catch (e) {
      const err = e as { message?: string; data?: Record<string, string[] | string> };
      const fields: LateFormErrors = {};
      for (const k of ["reason", "explanation", "document", "date"] as const) {
        const v = err.data?.[k];
        if (v && k !== "date") fields[k] = Array.isArray(v) ? v[0] : String(v);
      }
      setErrors(fields);
      setMsg(err.message ?? "Could not submit. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  const label = (text: string, required = false) => (
    <label className="field-label">{text}{required && <span style={{ color: "var(--error)" }}> *</span>}</label>
  );
  const fieldErr = (m?: string) => m ? <div style={{ color: "var(--error)", fontSize: 12, marginTop: 4 }}>{m}</div> : null;

  return (
    <Modal title={existing ? "Resubmit late arrival justification" : "Explain late arrival"} onClose={props.onClose}
      closeDisabled={busy}
      footer={<>
        <button className="btn btn-ghost" onClick={props.onClose} disabled={busy}>Cancel</button>
        <button className="btn btn-filled" onClick={submit} disabled={busy}>
          {busy ? "Submitting…" : existing ? "Resubmit" : "Submit"}
        </button>
      </>}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14, fontSize: 13 }}>
        {msg && <div className="alert alert-error">{msg}</div>}
        <div style={{ background: "var(--bg-low)", borderRadius: 8, padding: "8px 12px" }}>
          <strong>{fmtDate(date)}</strong>
          {(existing?.original_in || (props.mode === "new" && props.clockIn)) && (
            <span style={{ color: "var(--on-variant)" }}> · clocked in at {existing?.original_in ?? (props.mode === "new" ? props.clockIn : "")}</span>
          )}
          <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
            Your punch times stay as recorded. If approved, the day shows as Late (Excused) and doesn&apos;t count as a late mark.
          </div>
        </div>

        {existing?.rejection_reason && (
          <div className="alert alert-warn">
            <span><strong>Reviewer&apos;s note:</strong> {existing.rejection_reason}
              {existing.resubmit_by && <> — resubmit by {fmtDate(existing.resubmit_by)}</>}</span>
          </div>
        )}

        <div className="field-group">
          {label("Reason", true)}
          <select className="field-input" value={reason} onChange={e => { setReason(e.target.value as LateReason); setErrors({}); }}>
            {LATE_REASONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
          {fieldErr(errors.reason)}
        </div>

        <div className="field-group">
          {label("Explanation", true)}
          <textarea className="field-input" style={{ minHeight: 84 }} maxLength={EXPLANATION_MAX} value={explanation}
            placeholder="What happened? e.g. visited the doctor before work"
            onChange={e => { setExplanation(e.target.value); setErrors(x => ({ ...x, explanation: undefined })); }} />
          <div style={{ fontSize: 11, color: "var(--on-variant)", textAlign: "right" }}>{explanation.length}/{EXPLANATION_MAX}</div>
          {fieldErr(errors.explanation)}
        </div>

        <div className="field-group">
          {label(reason === "medical" ? "Medical proof" : "Supporting proof (optional)",
            reason === "medical" && !existing?.has_document)}
          <input className="field-input" type="file" accept={PROOF_ACCEPT}
            onChange={e => { setFile(e.target.files?.[0] ?? null); setErrors(x => ({ ...x, document: undefined })); }} />
          <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
            PDF, JPG or PNG, up to 5 MB — e.g. a doctor&apos;s note or prescription.
            {existing?.has_document && " Leave empty to keep the proof you already uploaded."}
            {" "}Only authorised HR can open medical proof; your manager sees the reason, not the file.
          </div>
          {fieldErr(errors.document)}
        </div>
      </div>
    </Modal>
  );
}
