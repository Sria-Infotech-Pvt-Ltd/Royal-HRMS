"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { usePermission } from "@/hooks/usePermission";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { getEffectiveBranch, isUnrestrictedUser } from "@/lib/auth";
import { canRequestCandidates, initialBranchRequest } from "@/lib/interviewListScope";
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
import InterviewHeader from "./InterviewHeader";
import CandidateStatCards from "./CandidateStatCards";
import CandidateToolbar from "./CandidateToolbar";
import { hasActiveFilters } from "./_filters";
import { FeedbackModal } from "./FeedbackModal";
import ConfirmModal from "@/components/ConfirmModal";
import { useT } from "@/hooks/useI18n";
import { tr } from "@/lib/i18n/tr";

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function InterviewListPage() {
  const t = useT();
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
  // The HR dashboard's "Add Candidate" shortcut links here with ?action=add; it only opens the form for someone who may create.
  useEffect(() => {
    if (canCreate && new URLSearchParams(window.location.search).get("action") === "add") setShowAdd(true);
  }, [canCreate]);
  const [showBulkImport, setShowBulkImport] = useState(false);
  const [markData,      setMarkData]      = useState<{ candidate: Candidate; targetStatus: "selected" | "rejected" } | null>(null);
  const [logsFor,       setLogsFor]       = useState<Candidate | null>(null);
  const [sendingPortal, setSendingPortal] = useState<number | null>(null);
  const [portalMsg,     setPortalMsg]     = useState<string | null>(null);
  const [portalErr,     setPortalErr]     = useState<string | null>(null);
  const [editTarget,    setEditTarget]    = useState<Candidate | null>(null);
  const [feedbackFor, setFeedbackFor] = useState<Candidate | null>(null);
  const [portalConfirm, setPortalConfirm] = useState<Candidate | null>(null);

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
    // A restricted user with no branch gets no candidate request at all (the server would not restrict them).
    if (!canRequestCandidates({ unrestricted, effectiveBranch })) {
      setCandidates([]);
      setLoading(false);
      return;
    }
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
      setError(tr("Failed to load candidates."));
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
  }, [unrestricted, effectiveBranch]);

  // Wait for the user (and, if branch-restricted, the branch list) to resolve before the very first fetch.
  // A restricted user whose own branch is unknown makes no request at all (fail closed). If the branch LIST is merely
  // unavailable to them, the request carries no branch and the server applies their own branch (lib/interviewListScope.ts).
  useEffect(() => {
    if (initialFetchDone.current || !user || !branchesLoaded) return;
    initialFetchDone.current = true;
    // When the branch list was refused (no branches.view) there is no branch id: send none, and the server scopes the
    // candidates to the signed-in user's own branch (see lib/interviewListScope.ts for why that is safe).
    const initial = initialBranchRequest({ unrestricted, effectiveBranch, branchId: myBranch ? myBranch.id : null });
    if (!unrestricted) setBranchFilter(initial.branch);
    fetchAll(search, statusFilter, initial.branch, 1);
  }, [user, branchesLoaded, unrestricted, effectiveBranch, myBranch, fetchAll, search, statusFilter]);

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

  async function confirmSendPortalLogin() {
    if (!portalConfirm) return;
    const candidateId = portalConfirm.id;
    setPortalConfirm(null);
    setSendingPortal(candidateId);
    setPortalMsg(null);
    setPortalErr(null);
    try {
      const res = await RECRUITMENT_API.sendPortalLogin(candidateId);
      setPortalMsg(res.data?.message ?? t("Onboarding link sent."));
      fetchAll(search, statusFilter, branchFilter);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? t("Failed to send the onboarding link.");
      setPortalErr(msg);
    } finally {
      setSendingPortal(null);
    }
  }

  const activeBranch = branches.find(b => b.id === branchFilter);

  const hasFilters = hasActiveFilters(search, statusFilter, branchFilter, unrestricted);

  function clearFilters() {
    const nextBranch = unrestricted ? "" : branchFilter;
    setSearch("");
    setStatusFilter("");
    setBranchFilter(nextBranch);
    fetchAll("", "", nextBranch, 1);
  }

  return (
    <div className="cand-page">
      <InterviewHeader
        branchName={activeBranch?.branch_name}
        canCreate={canCreate}
        onBulkImport={() => setShowBulkImport(true)}
        onAdd={() => setShowAdd(true)}
      />

      <CandidateStatCards
        stats={stats}
        branchName={activeBranch?.branch_name}
        activeStatus={statusFilter}
        onSelect={handleStatusFilter}
      />

      <CandidateToolbar
        search={search}
        onSearch={handleSearch}
        branches={branches}
        branchFilter={branchFilter}
        onBranch={handleBranchFilter}
        canChooseBranch={unrestricted}
        lockedBranch={effectiveBranch}
        statusFilter={statusFilter}
        statusChoices={statusChoices}
        onStatus={handleStatusFilter}
        hasFilters={hasFilters}
        onClear={clearFilters}
      />

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

      {/* Table */}
      <CandidateTable
        candidates={candidates}
        loading={loading}
        error={error}
        activeBranch={activeBranch}
        totalCount={totalCount}
        hasFilters={hasFilters}
        onClearFilters={clearFilters}
        statusChoices={statusChoices}
        canEditRec={canEditRec}
        sendingPortal={sendingPortal}
        page={page}
        totalPages={totalPages}
        onPageChange={handlePageChange}
        onOpenLogs={setLogsFor}
        onEdit={setEditTarget}
        onStatusChanged={onStatusChanged}
        onMarkRequest={(cand, status) => setMarkData({ candidate: cand, targetStatus: status })}
        onSendPortalLogin={setPortalConfirm}
        onOpenFeedback={setFeedbackFor}
      />

      {portalConfirm && (
        <ConfirmModal
          title={t("Send onboarding link?")}
          body={t("This emails {name} ({email}) a one-time link, valid for a limited time, to complete the onboarding wizard and upload documents. No account or password is created until you approve the onboarding.", { name: portalConfirm.name, email: portalConfirm.email })}
          confirmLabel={t("Send Link")}
          saving={sendingPortal === portalConfirm.id}
          onConfirm={confirmSendPortalLogin}
          onCancel={() => setPortalConfirm(null)}
        />
      )}

      {feedbackFor && <FeedbackModal candidateId={feedbackFor.id} candidateName={feedbackFor.name} onClose={() => setFeedbackFor(null)} />}

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
              showToast(t("Interview details saved. Invitation email sent to candidate."), "success");
            } else {
              showToast(t("Interview details updated."), "success");
            }
          }}
        />
      )}
    </div>
  );
}
