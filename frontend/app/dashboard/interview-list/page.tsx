"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { usePermission } from "@/hooks/usePermission";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { getEffectiveBranch, isUnrestrictedUser } from "@/lib/auth";
import {
  Branch,
  Candidate,
  CandidateStatus,
  RECRUITMENT_API,
  RecruitmentStats,
  fmtDate,
  initials,
  MODE_LABELS,
} from "./_data";
import { AddCandidateModal }          from "./AddCandidateModal";
import { MarkCandidateModal }         from "./MarkCandidateModal";
import { LogsModal }                  from "./LogsModal";
import { EditCandidateModal }         from "./EditCandidateModal";
import { CandidateBulkImportModal }   from "./CandidateBulkImportModal";

// ─── Tiny helpers ─────────────────────────────────────────────────────────────

const STATUS_META: Record<CandidateStatus, { label: string; cls: string; icon: string }> = {
  pending:              { label: "Pending",            cls: "badge-neutral", icon: "ti-clock" },
  screening:            { label: "Screening",          cls: "badge-info",    icon: "ti-eye" },
  interview_scheduled:  { label: "Interview Scheduled",cls: "badge-info",    icon: "ti-calendar" },
  interview_done:       { label: "Interview Done",     cls: "badge-warn",    icon: "ti-clipboard-check" },
  selected:             { label: "Selected",           cls: "badge-success", icon: "ti-check" },
  offer_sent:           { label: "Offer Sent",         cls: "badge-success", icon: "ti-send" },
  rejected:             { label: "Rejected",           cls: "badge-error",   icon: "ti-x" },
  converted:            { label: "Converted",          cls: "badge-neutral", icon: "ti-user-check" },
};

function StatusBadge({ status }: { status: CandidateStatus }) {
  const meta = STATUS_META[status] ?? STATUS_META.pending;
  return (
    <span className={`badge ${meta.cls}`}>
      <i className={`ti ${meta.icon}`} /> {meta.label}
    </span>
  );
}

function StatusDropdown({
  candidate,
  choices,
  onChanged,
  onMarkRequest,
}: {
  candidate: Candidate;
  choices: { value: CandidateStatus; label: string }[];
  onChanged: (updated: Candidate) => void;
  onMarkRequest: (candidate: Candidate, targetStatus: "selected" | "rejected") => void;
}) {
  const [updating, setUpdating] = useState(false);

  if (choices.length === 0) return null;

  // Ensure current status is always visible even if not in the choices list
  const hasCurrentStatus = choices.some(o => o.value === candidate.status);
  const options = hasCurrentStatus
    ? choices
    : [{ value: candidate.status, label: STATUS_META[candidate.status]?.label ?? candidate.status }, ...choices];

  async function handleChange(newStatus: CandidateStatus) {
    if (newStatus === candidate.status) return;
    // selected / rejected go through the modal (email template + preview)
    if (newStatus === "selected" || newStatus === "rejected") {
      onMarkRequest(candidate, newStatus);
      return;
    }
    setUpdating(true);
    try {
      const res = await RECRUITMENT_API.setStatus(candidate.id, { status: newStatus });
      onChanged(res.data?.data ?? { ...candidate, status: newStatus });
    } catch {
      // silently ignore — table will reflect current state on next load
    } finally {
      setUpdating(false);
    }
  }

  return (
    <select
      className="field-input field-select"
      style={{ fontSize: ".78rem", padding: "4px 28px 4px 8px", minWidth: 140, opacity: updating ? 0.6 : 1 }}
      value={candidate.status}
      disabled={updating}
      onChange={e => handleChange(e.target.value as CandidateStatus)}
      suppressHydrationWarning
    >
      {options.map(o => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}

function Avatar({ name, size = 32 }: { name: string; size?: number }) {
  return (
    <div className="user-avatar" style={{ width: size, height: size, fontSize: size * 0.38, flexShrink: 0 }}>
      {initials(name)}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function InterviewListPage() {
  const { showToast }  = useToast();
  const canCreate      = usePermission("recruitment.create");
  const canEditRec     = usePermission("recruitment.edit");
  const user            = useCurrentUser();
  const unrestricted    = isUnrestrictedUser(user);
  const effectiveBranch = getEffectiveBranch(user);
  const [candidates,    setCandidates]    = useState<Candidate[]>([]);
  const [stats,         setStats]         = useState<RecruitmentStats | null>(null);
  const [loading,       setLoading]       = useState(true);
  const [error,         setError]         = useState("");

  const [search,        setSearch]        = useState("");
  const [statusFilter,  setStatusFilter]  = useState<"" | CandidateStatus>("");
  const [branchFilter,  setBranchFilter]  = useState<number | "">("");
  const [branches,      setBranches]      = useState<Branch[]>([]);

  const [statusChoices, setStatusChoices] = useState<{ value: CandidateStatus; label: string }[]>([]);
  const [page,          setPage]          = useState(1);
  const [totalPages,    setTotalPages]    = useState(1);
  const [totalCount,    setTotalCount]    = useState(0);

  const [showAdd,       setShowAdd]       = useState(false);
  const [showBulkImport, setShowBulkImport] = useState(false);
  const [markData,      setMarkData]      = useState<{ candidate: Candidate; targetStatus: "selected" | "rejected" } | null>(null);
  const [logsFor,       setLogsFor]       = useState<Candidate | null>(null);
  const [sendingPortal, setSendingPortal] = useState<number | null>(null);
  const [portalMsg,     setPortalMsg]     = useState<string | null>(null);
  const [portalErr,     setPortalErr]     = useState<string | null>(null);
  const [editTarget,    setEditTarget]    = useState<Candidate | null>(null);

  const searchRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const initialFetchDone = useRef(false);

  const [branchesLoaded, setBranchesLoaded] = useState(false);

  // Fetch active branches once on mount
  useEffect(() => {
    clientApi
      .get<{ data: { results: Branch[] } }>(API.branches.list, {
        params: { status: "active", page_size: 100 },
      })
      .then(r => setBranches(r.data?.data?.results ?? []))
      .catch(() => {})
      .finally(() => setBranchesLoaded(true));
  }, []);

  // Branch-restricted users (everyone except system_admin) only ever see
  // their own branch — the id that matches their branch name in the list.
  const myBranch = branches.find(b => b.branch_name === effectiveBranch);

  const fetchAll = useCallback(async (
    q?: string,
    s?: string,
    b?: number | "",
    p?: number,
  ) => {
    setLoading(true);
    setError("");
    try {
      const cRes = await RECRUITMENT_API.list({
        search: q || undefined,
        status: s || undefined,
        branch: b || undefined,
        page:   p ?? 1,
      });
      const raw = cRes.data?.data;
      setCandidates(Array.isArray(raw?.results) ? raw.results : []);
      setTotalPages(raw?.total_pages ?? 1);
      setTotalCount(raw?.count ?? 0);
      setPage(raw?.page ?? 1);
      if (raw?.status_choices?.length) setStatusChoices(raw.status_choices);
    } catch {
      setError("Failed to load candidates.");
      setCandidates([]);
    } finally {
      setLoading(false);
    }
    try {
      const sRes = await RECRUITMENT_API.stats();
      setStats(sRes.data?.data ?? null);
    } catch {
      // stats are cosmetic — ignore failure
    }
  }, []);

  // Wait for the user (and, if branch-restricted, the branch list) to resolve
  // before the very first fetch — otherwise it would briefly go out unscoped.
  // If a restricted user's branch name has no matching Branch record, fail
  // closed (fetch nothing) rather than falling back to "All Branches".
  useEffect(() => {
    if (initialFetchDone.current || !user || !branchesLoaded) return;
    initialFetchDone.current = true;
    const initialBranch = unrestricted ? "" : (myBranch ? myBranch.id : -1);
    if (!unrestricted) setBranchFilter(initialBranch);
    fetchAll(search, statusFilter, initialBranch, 1);
  }, [user, branchesLoaded, unrestricted, myBranch, fetchAll, search, statusFilter]);

  function handleSearch(val: string) {
    setSearch(val);
    if (searchRef.current) clearTimeout(searchRef.current);
    searchRef.current = setTimeout(() => fetchAll(val, statusFilter, branchFilter, 1), 350);
  }

  function handleStatusFilter(val: "" | CandidateStatus) {
    setStatusFilter(val);
    fetchAll(search, val, branchFilter, 1);
  }

  function handleBranchFilter(val: number | "") {
    setBranchFilter(val);
    fetchAll(search, statusFilter, val, 1);
  }

  function handlePageChange(newPage: number) {
    fetchAll(search, statusFilter, branchFilter, newPage);
  }

  function onCandidateAdded(_c: Candidate) {
    setShowAdd(false);
    fetchAll(search, statusFilter, branchFilter, 1);
  }

  function onStatusChanged(updated: Candidate) {
    setCandidates(prev => prev.map(c => c.id === updated.id ? updated : c));
    setMarkData(null);
    fetchAll(search, statusFilter, branchFilter, page);
  }

  async function handleSendPortalLogin(candidateId: number) {
    setSendingPortal(candidateId);
    setPortalMsg(null);
    setPortalErr(null);
    try {
      const res = await RECRUITMENT_API.sendPortalLogin(candidateId);
      setPortalMsg(res.data?.message ?? "Portal login sent.");
      fetchAll(search, statusFilter, branchFilter);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Failed to send portal login.";
      setPortalErr(msg);
    } finally {
      setSendingPortal(null);
    }
  }

  const activeBranch = branches.find(b => b.id === branchFilter);

  const statCards = [
    { label: "Total",    value: stats?.total    ?? "—", icon: "ti-users",      iconCls: "si-primary" },
    { label: "Pending",  value: stats?.pending  ?? "—", icon: "ti-clock",      iconCls: "si-warn" },
    { label: "Selected", value: stats?.selected ?? "—", icon: "ti-user-check", iconCls: "si-success" },
    { label: "Rejected", value: stats?.rejected ?? "—", icon: "ti-user-x",     iconCls: "si-error" },
  ];

  return (
    <>
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="page-title">Interview List</div>
          <div className="page-sub">
            {activeBranch
              ? <>Showing candidates for <strong>{activeBranch.branch_name}</strong></>
              : "Manage all interview candidates and their status"}
          </div>
        </div>
        <div className="page-actions" style={{ gap: 10 }}>
          {/* Search */}
          <div className="search-bar">
            <i className="ti ti-search" />
            <input
              placeholder="Search candidates…"
              value={search}
              onChange={e => handleSearch(e.target.value)}
              suppressHydrationWarning
            />
          </div>

          {/* Branch filter dropdown — locked to their own branch for branch-restricted users */}
          <div style={{ position: "relative", display: "flex", alignItems: "center", gap: 6 }}>
            {unrestricted ? (
              <>
                <select
                  className="field-input field-select"
                  style={{ minWidth: 180, paddingLeft: 32 }}
                  value={branchFilter}
                  onChange={e => handleBranchFilter(e.target.value ? Number(e.target.value) : "")}
                  suppressHydrationWarning
                >
                  <option value="">All Branches</option>
                  {branches.map(b => (
                    <option key={b.id} value={b.id}>
                      {b.branch_name} ({b.branch_code})
                    </option>
                  ))}
                </select>
                <i
                  className="ti ti-building"
                  style={{
                    position: "absolute", left: 10, top: "50%",
                    transform: "translateY(-50%)", color: "var(--on-variant)",
                    pointerEvents: "none",
                  }}
                />
              </>
            ) : (
              <select
                className="field-input field-select"
                style={{ minWidth: 180, paddingLeft: 32, background: "var(--bg-low)", cursor: "not-allowed" }}
                value={effectiveBranch}
                disabled
                title="Scoped to your branch"
                suppressHydrationWarning
              >
                <option value={effectiveBranch}>{effectiveBranch || "—"}</option>
              </select>
            )}
            {!unrestricted && <i className="ti ti-lock" style={{ color: "var(--on-variant)", fontSize: 14 }} />}
          </div>

          {canCreate && (
            <>
              <button className="btn btn-ghost" onClick={() => setShowBulkImport(true)} suppressHydrationWarning>
                <i className="ti ti-file-upload" /> Bulk Import
              </button>
              <button className="btn btn-filled" onClick={() => setShowAdd(true)}>
                <i className="ti ti-plus" /> Add Candidate
              </button>
            </>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="stats-grid">
        {statCards.map(s => (
          <div key={s.label} className="stat-card">
            <div className={`stat-icon ${s.iconCls}`}><i className={`ti ${s.icon}`} /></div>
            <div className="stat-label">{s.label}</div>
            <div className="stat-value">{s.value}</div>
          </div>
        ))}
      </div>

      {/* Portal login feedback */}
      {portalMsg && (
        <div className="alert alert-success" style={{ marginBottom: 16 }}>
          <i className="ti ti-circle-check" /><div>{portalMsg}</div>
          <button style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer" }} onClick={() => setPortalMsg(null)}>✕</button>
        </div>
      )}
      {portalErr && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>
          <i className="ti ti-alert-circle" /><div>{portalErr}</div>
          <button style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer" }} onClick={() => setPortalErr(null)}>✕</button>
        </div>
      )}

      {/* Info banner */}
      <div className="alert alert-info" style={{ marginBottom: 16 }}>
        <i className="ti ti-info-circle" />
        <div>Move candidates through the pipeline stages. Send portal login to selected candidates so they can fill their onboarding wizard.</div>
      </div>

      {/* Table */}
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
            onChange={e => handleStatusFilter(e.target.value as "" | CandidateStatus)}
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
              <p>{activeBranch ? "Add a candidate to this branch to get started." : "Add a candidate or adjust your filters."}</p>
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Candidate</th><th>Position</th><th>Branch</th>
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
                        <button className="btn btn-ghost btn-sm" onClick={() => setLogsFor(c)}>
                          <i className="ti ti-history" /> Logs
                        </button>

                        {/* Edit — update interview details; not applicable once converted to an employee */}
                        {canEditRec && c.status !== "converted" && (
                          <button className="btn btn-ghost btn-sm" onClick={() => setEditTarget(c)} suppressHydrationWarning
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
                            onMarkRequest={(cand, status) => setMarkData({ candidate: cand, targetStatus: status })}
                          />
                        )}

                        {/* Selected: send onboarding portal login */}
                        {canEditRec && c.status === "selected" && (
                          <button
                            className="btn btn-filled btn-sm"
                            style={{ fontSize: ".78rem" }}
                            onClick={() => handleSendPortalLogin(c.id)}
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
                onClick={() => handlePageChange(page - 1)}
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
                      onClick={() => handlePageChange(p)}
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
                onClick={() => handlePageChange(page + 1)}
                disabled={page >= totalPages || loading}
                suppressHydrationWarning
              >
                Next <i className="ti ti-chevron-right" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Modals */}
      {showAdd && <AddCandidateModal onClose={() => setShowAdd(false)} onSaved={onCandidateAdded} />}
      {showBulkImport && (
        <CandidateBulkImportModal
          onClose={() => setShowBulkImport(false)}
          onSuccess={() => fetchAll(search, statusFilter, branchFilter, 1)}
        />
      )}
      {markData && (
        <MarkCandidateModal
          candidate={markData.candidate}
          targetStatus={markData.targetStatus}
          onClose={() => setMarkData(null)}
          onConfirmed={onStatusChanged}
        />
      )}
      {logsFor && <LogsModal candidate={logsFor} onClose={() => setLogsFor(null)} />}
      {editTarget && (
        <EditCandidateModal
          candidate={editTarget}
          branches={branches}
          onClose={() => setEditTarget(null)}
          onSaved={updated => {
            const hadDate = !!editTarget.interview_date;
            const nowHasDate = !!updated.interview_date;
            setCandidates(prev => prev.map(c => c.id === updated.id ? updated : c));
            setEditTarget(null);
            if (!hadDate && nowHasDate) {
              showToast("Interview details saved. Invitation email sent to candidate.", "success");
            } else {
              showToast("Interview details updated.", "success");
            }
          }}
        />
      )}
    </>
  );
}
