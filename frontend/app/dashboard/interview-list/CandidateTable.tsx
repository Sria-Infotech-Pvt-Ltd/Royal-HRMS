"use client";

import { Branch, Candidate, CandidateStatus } from "./_data";
import { interviewSummary, needsDetails } from "./_filters";
import { Avatar, StatusBadge, StatusDropdown } from "./_pageHelpers";

interface CandidateTableProps {
  candidates: Candidate[];
  loading: boolean;
  error: string;
  activeBranch: Branch | undefined;
  totalCount: number;
  hasFilters: boolean;
  onClearFilters: () => void;
  statusChoices: { value: CandidateStatus; label: string }[];
  canEditRec: boolean;
  sendingPortal: number | null;
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onOpenLogs: (candidate: Candidate) => void;
  onEdit: (candidate: Candidate) => void;
  onStatusChanged: (updated: Candidate) => void;
  onMarkRequest: (candidate: Candidate, targetStatus: "selected" | "rejected") => void;
  onSendPortalLogin: (candidate: Candidate) => void;
  onOpenFeedback: (candidate: Candidate) => void;
}

export default function CandidateTable({
  candidates, loading, error, activeBranch, totalCount, hasFilters, onClearFilters, statusChoices,
  canEditRec, sendingPortal, page, totalPages, onPageChange,
  onOpenLogs, onEdit, onStatusChanged, onMarkRequest, onSendPortalLogin, onOpenFeedback,
}: CandidateTableProps) {
  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">
          <i className="ti ti-users" />
          {activeBranch ? `${activeBranch.branch_name} Candidates` : "All Candidates"} ({totalCount})
        </span>
        <span className="cand-hint" title="Move candidates through the stages. Selected candidates receive the nine-step self-service onboarding wizard; direct hires use the HR hiring form and skip it.">
          <i className="ti ti-info-circle" aria-hidden="true" /> How the pipeline works
        </span>
      </div>

      {error && (
        <div className="alert alert-error" style={{ margin: "0 20px 16px" }}>
          <i className="ti ti-alert-circle" /><div>{error}</div>
        </div>
      )}

      <div className="table-wrap">
        {loading ? (
          <div className="cand-skeleton" role="status" aria-label="Loading candidates">
            {[0, 1, 2, 3, 4].map(row => (
              <div key={row} className="cand-skeleton-row">
                <span className="cand-skeleton-dot" /><span className="cand-skeleton-bar" /><span className="cand-skeleton-bar short" />
              </div>
            ))}
          </div>
        ) : !Array.isArray(candidates) || candidates.length === 0 ? (
          <div className="empty-state cand-empty">
            <i className={`ti ${hasFilters ? "ti-search-off" : "ti-users"}`} />
            <h3>
              {hasFilters ? "No candidates match your filters"
                : activeBranch ? `No candidates in ${activeBranch.branch_name}` : "No candidates yet"}
            </h3>
            <p>
              {hasFilters ? "Try a different search or stage, or clear the filters to see everyone."
                : "Add a candidate or bulk-import a sheet to start building your pipeline."}
            </p>
            {hasFilters && (
              <button type="button" className="btn btn-ghost" onClick={onClearFilters}>
                <i className="ti ti-filter-off" /> Clear filters
              </button>
            )}
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Candidate</th><th>Position</th><th>Company Code</th>
                <th>Interview</th><th>Status</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map(c => (
                <tr key={c.id}>
                  <td>
                    <div className="cand-person">
                      <Avatar name={c.name} size={32} />
                      <div className="cand-person-text">
                        <strong>{c.name}</strong>
                        <span>{c.email}</span>
                        {c.referral_by !== null && (
                          <div style={{ fontSize: 11, color: "var(--brand)", display: "flex", alignItems: "center", gap: 3, marginTop: 2 }}>
                            <i className="ti ti-user-plus" style={{ fontSize: 10 }} />
                            Referred by {c.referral_by_name || "Employee"}
                          </div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td>{c.position_applied}</td>
                  <td>
                    {c.branch_name
                      ? <span className="badge badge-neutral" style={{ fontSize: 11 }}>{c.branch_name}</span>
                      : <span className="text-xs text-[var(--on-variant)]">—</span>}
                  </td>
                  <td>
                    {(() => {
                      const summary = interviewSummary(c);
                      return summary.when ? (
                        <div className="cand-interview">
                          <strong>{summary.when}</strong>
                          <span>{summary.mode}{summary.interviewer ? ` · ${summary.interviewer}` : ""}</span>
                        </div>
                      ) : (
                        <div className="cand-interview"><span>Not scheduled</span><span>{summary.mode}</span></div>
                      );
                    })()}
                  </td>
                  <td><StatusBadge status={c.status} /></td>
                  <td>
                    <div className="cand-actions">
                      <button className="btn btn-ghost btn-sm cand-icon-btn" title="Activity log" aria-label={`Activity log for ${c.name}`} onClick={() => onOpenLogs(c)}>
                        <i className="ti ti-history" />
                      </button>

                      <button className="btn btn-ghost btn-sm cand-icon-btn" title="Interview feedback" aria-label={`Interview feedback for ${c.name}`} onClick={() => onOpenFeedback(c)}>
                        <i className="ti ti-message-2-star" />
                      </button>

                      {/* Edit — update interview details; not applicable once converted to an employee */}
                      {canEditRec && c.status !== "converted" && (
                        <button className="btn btn-ghost btn-sm" onClick={() => onEdit(c)} suppressHydrationWarning
                          style={needsDetails(c) ? { color: "var(--warn)" } : undefined}>
                          <i className="ti ti-pencil" />
                          {needsDetails(c) ? " Set Details" : " Edit"}
                        </button>
                      )}

                      {/* Status dropdown — only for pre-selection pipeline */}
                      {canEditRec && c.status !== "converted" && c.status !== "selected" && c.status !== "offer_sent" && (
                        <StatusDropdown
                          candidate={c}
                          choices={statusChoices}
                          onChanged={onStatusChanged}
                          onMarkRequest={onMarkRequest}
                        />
                      )}

                      {/* Selected: send the password-less onboarding link */}
                      {canEditRec && c.status === "selected" && (
                        <button
                          className="btn btn-filled btn-sm"
                          style={{ fontSize: ".78rem" }}
                          onClick={() => onSendPortalLogin(c)}
                          disabled={sendingPortal === c.id}
                          suppressHydrationWarning
                        >
                          {sendingPortal === c.id
                            ? <><i className="ti ti-loader-2 animate-spin" /> Sending…</>
                            : <><i className="ti ti-send" /> Send Onboarding Link</>
                          }
                        </button>
                      )}

                      {/* Offer sent: portal credentials already sent */}
                      {c.status === "offer_sent" && (
                        <span className="badge badge-success" style={{ fontSize: ".75rem" }}>
                          <i className="ti ti-mail-check" /> Link Sent
                        </span>
                      )}

                      {/* Converted to employee */}
                      {c.status === "converted" && (
                        <span className="badge badge-neutral" style={{ fontSize: ".75rem" }}>
                          <i className="ti ti-user-check" /> Employee
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 20px", borderTop: "1px solid var(--outline-v)" }}>
          <span style={{ fontSize: 13, color: "var(--on-variant)" }}>
            Page {page} of {totalPages} · {totalCount} total
          </span>
          <div style={{ display: "flex", gap: 6 }}>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1 || loading}
              suppressHydrationWarning
            >
              <i className="ti ti-chevron-left" /> Prev
            </button>
            {(() => {
              const delta = 1;
              const left  = Math.max(2, page - delta);
              const right = Math.min(totalPages - 1, page + delta);
              const items: (number | "ellipsis")[] = [1];
              if (left > 2) items.push("ellipsis");
              for (let p = left; p <= right; p++) items.push(p);
              if (right < totalPages - 1) items.push("ellipsis");
              if (totalPages > 1) items.push(totalPages);
              return items.map((p, idx) =>
                p === "ellipsis" ? (
                  <span key={`e${idx}`} style={{ padding: "0 6px", color: "var(--on-variant)" }}>…</span>
                ) : (
                  <button
                    key={p}
                    className={`btn btn-sm ${p === page ? "btn-filled" : "btn-ghost"}`}
                    onClick={() => onPageChange(p)}
                    disabled={loading}
                    suppressHydrationWarning
                    style={{ minWidth: 34 }}
                  >
                    {p}
                  </button>
                )
              );
            })()}
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages || loading}
              suppressHydrationWarning
            >
              Next <i className="ti ti-chevron-right" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
