"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
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
import { AddCandidateModal }  from "./AddCandidateModal";
import { MarkCandidateModal } from "./MarkCandidateModal";
import { LogsModal }          from "./LogsModal";

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
  const [candidates,    setCandidates]    = useState<Candidate[]>([]);
  const [stats,         setStats]         = useState<RecruitmentStats | null>(null);
  const [loading,       setLoading]       = useState(true);
  const [error,         setError]         = useState("");

  const [search,        setSearch]        = useState("");
  const [statusFilter,  setStatusFilter]  = useState<"" | CandidateStatus>("");
  const [branchFilter,  setBranchFilter]  = useState<number | "">("");
  const [branches,      setBranches]      = useState<Branch[]>([]);

  const [statusChoices, setStatusChoices] = useState<{ value: CandidateStatus; label: string }[]>([]);

  const [showAdd,   setShowAdd]   = useState(false);
  const [markData,  setMarkData]  = useState<{ candidate: Candidate; targetStatus: "selected" | "rejected" } | null>(null);
  const [logsFor,   setLogsFor]   = useState<Candidate | null>(null);
  const [sendingPortal, setSendingPortal] = useState<number | null>(null);
  const [portalMsg,     setPortalMsg]     = useState<string | null>(null);
  const [portalErr,     setPortalErr]     = useState<string | null>(null);

  const searchRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch active branches and status choices once on mount
  useEffect(() => {
    clientApi
      .get<{ data: { results: Branch[] } }>(API.branches.list, {
        params: { status: "active", page_size: 100 },
      })
      .then(r => setBranches(r.data?.data?.results ?? []))
      .catch(() => {});

    RECRUITMENT_API.getStatuses()
      .then(r => setStatusChoices(r.data?.data ?? []))
      .catch(() => {});
  }, []);

  const fetchAll = useCallback(async (
    q?: string,
    s?: string,
    b?: number | "",
  ) => {
    setLoading(true);
    setError("");
    try {
      const cRes = await RECRUITMENT_API.list({
        search: q   || undefined,
        status: s   || undefined,
        branch: b   || undefined,
      });
      const raw = cRes.data?.data;
      setCandidates(Array.isArray(raw?.results) ? raw.results : []);
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

  useEffect(() => { fetchAll(); }, [fetchAll]);

  function handleSearch(val: string) {
    setSearch(val);
    if (searchRef.current) clearTimeout(searchRef.current);
    searchRef.current = setTimeout(() => fetchAll(val, statusFilter, branchFilter), 350);
  }

  function handleStatusFilter(val: "" | CandidateStatus) {
    setStatusFilter(val);
    fetchAll(search, val, branchFilter);
  }

  function handleBranchFilter(val: number | "") {
    setBranchFilter(val);
    fetchAll(search, statusFilter, val);
  }

  function onCandidateAdded(c: Candidate) {
    setCandidates(prev => [c, ...prev]);
    setStats(prev => prev ? { ...prev, total: prev.total + 1, pending: prev.pending + 1 } : prev);
    setShowAdd(false);
  }

  function onStatusChanged(updated: Candidate) {
    setCandidates(prev => prev.map(c => c.id === updated.id ? updated : c));
    setMarkData(null);
    fetchAll(search, statusFilter, branchFilter);
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
          {/* Branch filter dropdown */}
          <div style={{ position: "relative" }}>
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
          </div>

          <button className="btn btn-filled" onClick={() => setShowAdd(true)}>
            <i className="ti ti-plus" /> Add Candidate
          </button>
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
            {activeBranch ? `${activeBranch.branch_name} Candidates` : "All Candidates"} ({candidates.length})
          </span>
          <div className="filter-bar" style={{ margin: 0 }}>
            <div className="search-bar">
              <i className="ti ti-search" />
              <input placeholder="Search candidate…" value={search} onChange={e => handleSearch(e.target.value)} suppressHydrationWarning />
            </div>
            <select
              className="field-input field-select"
              style={{ width: 180 }}
              value={statusFilter}
              onChange={e => handleStatusFilter(e.target.value as "" | CandidateStatus)}
              suppressHydrationWarning
            >
              <option value="">All Status</option>
              <option value="pending">Pending</option>
              <option value="screening">Screening</option>
              <option value="interview_scheduled">Interview Scheduled</option>
              <option value="interview_done">Interview Done</option>
              <option value="selected">Selected</option>
              <option value="offer_sent">Offer Sent</option>
              <option value="rejected">Rejected</option>
              <option value="converted">Converted</option>
            </select>
          </div>
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

                        {/* Status dropdown — only for pre-selection pipeline */}
                        {c.status !== "converted" && c.status !== "selected" && c.status !== "offer_sent" && (
                          <StatusDropdown
                            candidate={c}
                            choices={statusChoices}
                            onChanged={onStatusChanged}
                            onMarkRequest={(cand, status) => setMarkData({ candidate: cand, targetStatus: status })}
                          />
                        )}

                        {/* Selected: show Send Login button */}
                        {c.status === "selected" && (
                          <button
                            className="btn btn-filled btn-sm"
                            style={{ fontSize: ".78rem" }}
                            onClick={() => handleSendPortalLogin(c.id)}
                            disabled={sendingPortal === c.id}
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
      </div>

      {/* Modals */}
      {showAdd && <AddCandidateModal onClose={() => setShowAdd(false)} onSaved={onCandidateAdded} />}
      {markData && (
        <MarkCandidateModal
          candidate={markData.candidate}
          targetStatus={markData.targetStatus}
          onClose={() => setMarkData(null)}
          onConfirmed={onStatusChanged}
        />
      )}
      {logsFor && <LogsModal candidate={logsFor} onClose={() => setLogsFor(null)} />}
    </>
  );
}
