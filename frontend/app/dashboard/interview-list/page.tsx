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
} from "./_data";
import { AddCandidateModal }          from "./AddCandidateModal";
import { MarkCandidateModal }         from "./MarkCandidateModal";
import { LogsModal }                  from "./LogsModal";
import { EditCandidateModal }         from "./EditCandidateModal";
import { CandidateBulkImportModal }   from "./CandidateBulkImportModal";
import CandidateTable from "./CandidateTable";

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
                  <option value="">All Company Codes</option>
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
                title="Scoped to your Company Code"
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
      <CandidateTable
        candidates={candidates}
        loading={loading}
        error={error}
        activeBranch={activeBranch}
        totalCount={totalCount}
        statusFilter={statusFilter}
        statusChoices={statusChoices}
        onStatusFilter={handleStatusFilter}
        canEditRec={canEditRec}
        sendingPortal={sendingPortal}
        page={page}
        totalPages={totalPages}
        onPageChange={handlePageChange}
        onOpenLogs={setLogsFor}
        onEdit={setEditTarget}
        onStatusChanged={onStatusChanged}
        onMarkRequest={(cand, status) => setMarkData({ candidate: cand, targetStatus: status })}
        onSendPortalLogin={handleSendPortalLogin}
      />

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
