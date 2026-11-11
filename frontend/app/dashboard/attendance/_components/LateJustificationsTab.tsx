"use client";

// HR Attendance → Late Justifications: every late-arrival justification the
// user may review (same scope as the corrections queue), filtered by status
// or missing proof. Click a row to review.

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { LATE_STATUS } from "@/lib/lateJustification";
import type { LateJustificationRow } from "@/types/lateJustification";
import LateJustificationReviewModal from "./LateJustificationReviewModal";

const FILTERS = [
  { key: "",          label: "All" },
  { key: "pending",   label: "Pending" },
  { key: "approved",  label: "Approved" },
  { key: "rejected",  label: "Rejected" },
  { key: "resubmit",  label: "Resubmission Required" },
  { key: "missing",   label: "Missing Proof" },
] as const;

function fmtDate(iso: string) {
  return new Date(iso + "T12:00:00").toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export default function LateJustificationsTab() {
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["key"]>("pending");
  const [open, setOpen] = useState<LateJustificationRow | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const query = filter === "missing" ? "&missing_proof=true" : filter === "pending" ? "" : filter ? `&status=${filter}` : "";
  const { data, loading, error, refetch } = useFetch<{ results: LateJustificationRow[] }>(
    `${API.attendance.corrections}?kind=late_justification&page_size=100${query}`);
  // "Pending" covers both stages (manager and HR).
  const rows = (data?.results ?? []).filter(r => filter !== "pending" || r.status === "pending" || r.status === "l2_pending");

  return (
    <div className="card">
      <div className="card-header" style={{ flexWrap: "wrap", gap: 8 }}>
        <div className="card-title"><i className="ti ti-message-question" /> Late Arrival Justifications</div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {FILTERS.map(f => (
            <button key={f.key} className={`btn btn-sm ${filter === f.key ? "btn-filled" : "btn-ghost"}`} onClick={() => setFilter(f.key)}>
              {f.label}
            </button>
          ))}
        </div>
      </div>
      {notice && <div className="alert alert-success" style={{ margin: 12 }}><i className="ti ti-circle-check" /> {notice}</div>}
      {error && <div className="alert alert-error" style={{ margin: 12 }}>{error}</div>}
      <div className="table-wrap">
        {loading ? (
          <div style={{ padding: "30px 20px", textAlign: "center" }}><i className="ti ti-loader-2 spin" /></div>
        ) : rows.length === 0 ? (
          <div className="empty-state"><i className="ti ti-message-question" /><h3>No requests</h3><p>Nothing matches this filter.</p></div>
        ) : (
          <table>
            <thead>
              <tr><th>Employee</th><th>Date</th><th>Clock-In</th><th>Reason</th><th>Proof</th><th>Status</th><th style={{ textAlign: "right" }}>Action</th></tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id} onClick={() => { setNotice(null); setOpen(r); }} style={{ cursor: "pointer" }}>
                  <td><strong>{r.name}</strong><div style={{ fontSize: 11, color: "var(--on-variant)" }}>{r.employee_id} · {r.branch || "—"}</div></td>
                  <td>{fmtDate(r.date)}</td>
                  <td className="font-mono text-xs">{r.original_in ?? "—"}</td>
                  <td>{r.reason_label}<div style={{ fontSize: 11, color: "var(--on-variant)", maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.explanation}</div></td>
                  <td>
                    {r.has_document
                      ? <span className="badge badge-neutral"><i className={`ti ${r.can_view_document ? "ti-file" : "ti-lock"}`} /> Attached</span>
                      : <span className={r.proof_required ? "badge badge-error" : "badge badge-neutral"}>{r.proof_required ? "Missing" : "None"}</span>}
                  </td>
                  <td><span className={LATE_STATUS[r.status].cls}>{LATE_STATUS[r.status].label}</span></td>
                  <td style={{ textAlign: "right" }}>
                    <button className={`btn btn-sm ${r.can_action ? "btn-filled" : "btn-ghost"}`}>{r.can_action ? "Review" : "View"}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {open && (
        <LateJustificationReviewModal request={open} onClose={() => setOpen(null)} onDone={m => { setNotice(m); refetch(); }} />
      )}
    </div>
  );
}
