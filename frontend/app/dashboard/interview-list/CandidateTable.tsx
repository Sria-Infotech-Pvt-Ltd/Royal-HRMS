"use client";

import { Branch, Candidate, CandidateStatus, fmtDate, MODE_LABELS } from "./_data";
import { Avatar, StatusBadge, StatusDropdown } from "./_pageHelpers";

interface CandidateTableProps {
  candidates: Candidate[];
  loading: boolean;
  error: string;
  activeBranch: Branch | undefined;
  totalCount: number;
  statusFilter: "" | CandidateStatus;
  statusChoices: { value: CandidateStatus; label: string }[];
  onStatusFilter: (val: "" | CandidateStatus) => void;
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
}

export default function CandidateTable({
  candidates, loading, error, activeBranch, totalCount, statusFilter, statusChoices,
  onStatusFilter, canEditRec, sendingPortal, page, totalPages, onPageChange,
  onOpenLogs, onEdit, onStatusChanged, onMarkRequest, onSendPortalLogin,
}: CandidateTableProps) {
  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">
          <i className="ti ti-users" />
          {activeBranch ? `${activeBranch.branch_name} Candidates` : "All Candidates"} ({totalCount})
        </span>
        <select
          className="field-input field-select"
          style={{ width: 180 }}
          value={statusFilter}
          onChange={e => onStatusFilter(e.target.value as "" | CandidateStatus)}
          suppressHydrationWarning
        >
          <option value="">All Status</option>
          {statusChoices.map(s => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
      </div>

      {error && (
        <div className="alert alert-error" style={{ margin: "0 20px 16px" }}>
          <i className="ti ti-alert-circle" /><div>{error}</div>
        </div>
      )}

      <div className="table-wrap">
        {loading ? (
          <div className="text-center py-10"><i className="ti ti-loader-2 spin text-3xl" /></div>
        ) : !Array.isArray(candidates) || candidates.length === 0 ? (
          <div className="empty-state">
            <i className="ti ti-users" />
            <h3>{activeBranch ? `No candidates in ${activeBranch.branch_name}` : "No candidates found"}</h3>
            <p>{activeBranch ? "Add a candidate to this Company Code to get started." : "Add a candidate or adjust your filters."}</p>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Candidate</th><th>Position</th><th>Company Code</th>
                <th>Interview Date</th><th>Mode</th><th>Status</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map(c => (
                <tr key={c.id}>
                  <td>
                    <div className="flex items-center gap-3">
                      <Avatar name={c.name} size={32} />
                      <div>
                        <strong>{c.name}</strong>
                        <div className="text-xs text-[var(--on-variant)]">{c.email}</div>
                        {c.referral_by !== null && (
                          <div style={{ fontSize: 11, color: "#7c3aed", display: "flex", alignItems: "center", gap: 3, marginTop: 2 }}>
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
                  <td>{fmtDate(c.interview_date)}</td>
                  <td><span className="text-xs">{MODE_LABELS[c.interview_mode]}</span></td>
                  <td><StatusBadge status={c.status} /></td>
                  <td>
                    <div className="flex items-center gap-2">
                      <button className="btn btn-ghost btn-sm" onClick={() => onOpenLogs(c)}>
                        <i className="ti ti-history" /> Logs
                      </button>

                      {/* Edit — update interview details; not applicable once converted to an employee */}
                      {canEditRec && c.status !== "converted" && (
                        <button className="btn btn-ghost btn-sm" onClick={() => onEdit(c)} suppressHydrationWarning
                          style={c.referral_by !== null && (!c.branch || !c.interview_date) ? { color: "var(--warn)" } : undefined}>
                          <i className="ti ti-pencil" />
                          {c.referral_by !== null && (!c.branch || !c.interview_date) ? " Set Details" : " Edit"}
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

                      {/* Selected: send onboarding portal login */}
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
                            : <><i className="ti ti-send" /> Send Login</>
                          }
                        </button>
                      )}

                      {/* Offer sent: portal credentials already sent */}
                      {c.status === "offer_sent" && (
                        <span className="badge badge-success" style={{ fontSize: ".75rem" }}>
                          <i className="ti ti-mail-check" /> Login Sent
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
