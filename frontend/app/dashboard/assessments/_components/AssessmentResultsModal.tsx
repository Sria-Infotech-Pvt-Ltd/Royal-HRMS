"use client";

import type { Assessment, AssessmentCandidate } from "../page";

function fmt(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function StatusBadge({ status }: { status: AssessmentCandidate["status"] }) {
  if (status === "complete")    return <span className="badge badge-success">Completed</span>;
  if (status === "in_progress") return <span className="badge badge-info">In Progress</span>;
  return <span className="badge" style={{ background: "var(--bg-mid)", color: "var(--on-variant)" }}>Pending</span>;
}

export default function AssessmentResultsModal({ assessment, onClose }: { assessment: Assessment; onClose: () => void }) {
  const candidates = assessment.candidates ?? [];

  return (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 780 }}>
        <div className="modal-header">
          <div className="modal-title">
            <i className="ti ti-list-details mr-6" />Candidate Results — {assessment.title}
          </div>
          <button className="modal-close" onClick={onClose}><i className="ti ti-x" /></button>
        </div>

        <div className="modal-body" style={{ padding: 0 }}>
          {candidates.length === 0 ? (
            <div className="text-center py-12 text-sm text-[var(--on-variant)]">
              <i className="ti ti-clipboard text-2xl block mb-2" />
              No candidates have been assigned this assessment yet.
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ background: "var(--bg-mid, #f8fafc)", borderBottom: "1px solid var(--outline-v)" }}>
                    {["#", "Candidate", "Status", "Score", "Pass %", "Attempts", "Assigned On", "Completed At"].map(h => (
                      <th key={h} style={{ padding: "10px 14px", textAlign: "left", fontWeight: 600, color: "var(--on-variant)", whiteSpace: "nowrap" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((c, idx) => (
                    <tr key={c.id} style={{ borderBottom: "1px solid var(--outline-v)" }}>
                      <td style={{ padding: "12px 14px", color: "var(--on-variant)", fontWeight: 500 }}>{idx + 1}</td>
                      <td style={{ padding: "12px 14px" }}>
                        <div className="font-medium text-[var(--on-bg)]">{c.assignee_name}</div>
                        <div className="text-xs text-[var(--on-variant)]">{c.assignee_email}</div>
                      </td>
                      <td style={{ padding: "12px 14px" }}>
                        <StatusBadge status={c.status} />
                      </td>
                      <td style={{ padding: "12px 14px" }}>
                        {c.status === "complete"
                          ? <span className="font-semibold">{c.score_awarded} / {c.pass_score}</span>
                          : <span className="text-[var(--on-variant)]">—</span>}
                      </td>
                      <td style={{ padding: "12px 14px" }}>
                        <span style={{ fontWeight: 600, color: c.pass_percentage === "N/A" ? "var(--on-variant)" : parseInt(c.pass_percentage) >= 100 ? "#16a34a" : "#dc2626" }}>
                          {c.pass_percentage}
                        </span>
                      </td>
                      <td style={{ padding: "12px 14px", textAlign: "center", fontWeight: 500 }}>{c.attempt_count}</td>
                      <td style={{ padding: "12px 14px", whiteSpace: "nowrap", color: "var(--on-variant)" }}>{fmt(c.created_at)}</td>
                      <td style={{ padding: "12px 14px", whiteSpace: "nowrap", color: "var(--on-variant)" }}>{fmt(c.completed_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
