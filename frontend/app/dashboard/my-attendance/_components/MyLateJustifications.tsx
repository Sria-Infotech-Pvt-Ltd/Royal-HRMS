"use client";

// The employee's own late-arrival justifications: status, the reviewer's
// reason, their own proof, and Resubmit when a reviewer asked for it.

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { API_BASE } from "@/lib/config";
import DocPreviewModal from "@/components/DocPreviewModal";
import { LATE_STATUS } from "@/lib/lateJustification";
import type { LateJustificationRow } from "@/types/lateJustification";
import LateJustificationModal from "./LateJustificationModal";

function fmtDate(iso: string) {
  return new Date(iso + "T12:00:00").toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export default function MyLateJustifications() {
  const { data, loading, error, refetch } = useFetch<{ results: LateJustificationRow[] }>(
    `${API.attendance.myCorrections}?kind=late_justification&page_size=100`);
  const [resubmit, setResubmit] = useState<LateJustificationRow | null>(null);
  const [preview, setPreview] = useState<LateJustificationRow | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const rows = data?.results ?? [];

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-message-question" /> Late Arrival Justifications</div>
      </div>
      {notice && <div className="alert alert-success" style={{ margin: 12 }}><i className="ti ti-circle-check" /> {notice}</div>}
      {error && <div className="alert alert-error" style={{ margin: 12 }}>{error}</div>}
      <div className="table-wrap">
        {loading ? (
          <div style={{ padding: "30px 20px", textAlign: "center" }}><i className="ti ti-loader-2 spin" /></div>
        ) : rows.length === 0 ? (
          <div className="empty-state">
            <i className="ti ti-message-question" />
            <h3>No late arrival justifications</h3>
            <p>Use “Explain” on a late day in your attendance calendar (within 3 days).</p>
          </div>
        ) : (
          <table>
            <thead>
              <tr><th>Date</th><th>Clock-In</th><th>Reason</th><th>Proof</th><th style={{ textAlign: "center" }}>Status</th><th style={{ textAlign: "right" }}>Action</th></tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id}>
                  <td>{fmtDate(r.date)}</td>
                  <td className="font-mono text-xs">{r.original_in ?? "—"}</td>
                  <td>
                    {r.reason_label}
                    <div style={{ fontSize: 11, color: "var(--on-variant)", maxWidth: 260 }}>{r.explanation}</div>
                    {r.rejection_reason && (
                      <div style={{ fontSize: 11, color: "var(--error)", marginTop: 2 }}>Reviewer: {r.rejection_reason}</div>
                    )}
                  </td>
                  <td>
                    {r.has_document && r.can_view_document
                      ? <button className="btn btn-ghost btn-sm" onClick={() => setPreview(r)}><i className="ti ti-file" /> View</button>
                      : <span style={{ color: "var(--on-variant)" }}>—</span>}
                  </td>
                  <td style={{ textAlign: "center" }}>
                    <span className={LATE_STATUS[r.status].cls}>{r.status === "approved" ? "Late (Excused)" : LATE_STATUS[r.status].label}</span>
                  </td>
                  <td style={{ textAlign: "right" }}>
                    {r.can_resubmit && (
                      <button className="btn btn-filled btn-sm" onClick={() => { setNotice(null); setResubmit(r); }}>
                        <i className="ti ti-upload" /> Resubmit
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {resubmit && (
        <LateJustificationModal mode="resubmit" request={resubmit} onClose={() => setResubmit(null)}
          onSuccess={m => { setNotice(m); refetch(); }} />
      )}
      {preview && (
        <DocPreviewModal name={`Proof — ${fmtDate(preview.date)}`} fileName={preview.document_name}
          fileUrl={`${API_BASE}${API.attendance.correctionDocument(preview.id)}`} onClose={() => setPreview(null)} />
      )}
    </div>
  );
}
