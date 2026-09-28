"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { ApprovalModal } from "../ApprovalModal";
import { LeaveRequest } from "../../leave/_data";
import {
  ApprovalItem, ApprovalKind, CorrectionListResponse,
  DisplayStatus, ExpenseListResponse, ExpenseRequest, LeaveListResponse, SeparationListResponse, WfhListResponse,
  TYPE_TABS, correctionToItem, expenseToItem, leaveAutoVars, leaveToItem, separationToItem, toSortableTime, wfhToItem,
} from "../_data";
import SummaryCards from "./SummaryCards";
import ApprovalsToolbar from "./ApprovalsToolbar";
import ApprovalsTable from "./ApprovalsTable";
import RequestDetailDrawer from "./RequestDetailDrawer";
import BulkConfirmModal from "./BulkConfirmModal";

interface ModalState {
  id:            string;
  action:        "approve" | "reject";
  label:         string;
  kind:          "leave" | "expense";
  employeeName:  string;
  employeeEmail: string;
  autoVars?:     Record<string, string>;
}

export default function TeamApprovalsSection() {
  const router = useRouter();
  const { showToast } = useToast();

  // ── Data: fetch every kind up front (page_size capped at 100 server-side) —
  // the summary cards and the "All Requests" tab both need the full picture,
  // not just whatever the active tab happens to be looking at. ──
  const { data: leaveRaw,      loading: leaveLoading,      error: leaveError,      refetch: refetchLeave } =
    useFetch<LeaveListResponse>(`${API.approvals.leaveRequests}?scope=team&page_size=100`);
  const { data: expenseRaw,    loading: expenseLoading,    error: expenseError,    refetch: refetchExpense } =
    useFetch<ExpenseListResponse>(`${API.approvals.expenseList}?page_size=100`);
  const { data: correctionRaw, loading: correctionLoading, error: correctionError, refetch: refetchCorrections } =
    useFetch<CorrectionListResponse>(`${API.attendance.corrections}?page_size=100`);
  const { data: separationRaw, loading: separationLoading, error: separationError, refetch: refetchSeparation } =
    useFetch<SeparationListResponse>(`${API.separation.list}?scope=team&page_size=100`);
  const { data: wfhRaw,        loading: wfhLoading,        error: wfhError,        refetch: refetchWfh } =
    useFetch<WfhListResponse>(`${API.approvals.wfhRequests}?scope=team&page_size=100`);

  useEffect(() => {
    function handleLeaveUpdate() { refetchLeave(); }
    window.addEventListener("leave:updated", handleLeaveUpdate);
    return () => window.removeEventListener("leave:updated", handleLeaveUpdate);
  }, [refetchLeave]);

  function refetchAll() { refetchLeave(); refetchExpense(); refetchCorrections(); refetchSeparation(); refetchWfh(); }

  const allItems: ApprovalItem[] = useMemo(() => [
    ...(leaveRaw?.results ?? []).map(leaveToItem),
    ...(expenseRaw?.results ?? []).map(expenseToItem),
    ...(correctionRaw?.results ?? []).map(correctionToItem),
    ...(separationRaw?.results ?? []).map(separationToItem),
    ...(wfhRaw?.results ?? []).map(wfhToItem),
  ], [leaveRaw, expenseRaw, correctionRaw, separationRaw, wfhRaw]);

  const counts = useMemo(() => {
    const pendingOf = (kind: ApprovalKind) => allItems.filter(i => i.kind === kind && i.displayStatus === "pending").length;
    const leave = pendingOf("leave");
    const expense = pendingOf("expense");
    const correction = pendingOf("attendance_correction");
    const separation = pendingOf("separation");
    const wfh = pendingOf("wfh");
    return { leave, expense, correction, separation, wfh, pending: leave + expense + correction + separation + wfh };
  }, [allItems]);

  const tabCounts = useMemo(() => ({
    all: counts.pending,
    leave: counts.leave,
    expense: counts.expense,
    attendance_correction: counts.correction,
    separation: counts.separation,
    wfh: counts.wfh,
  }), [counts]);

  // ── Tabs + toolbar filter state ──
  const [activeTab,    setActiveTab]    = useState<"all" | ApprovalKind>("all");
  const [search,       setSearch]       = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | DisplayStatus>("pending");
  const [typeFilter,   setTypeFilter]   = useState<"all" | ApprovalKind>("all");
  const [dateFrom,     setDateFrom]     = useState("");
  const [dateTo,       setDateTo]       = useState("");
  const [selected,     setSelected]     = useState<Set<string>>(new Set());

  useEffect(() => { setSelected(new Set()); }, [activeTab]);

  const filteredItems = useMemo(() => {
    return allItems.filter(item => {
      if (activeTab !== "all" && item.kind !== activeTab) return false;
      if (activeTab === "all" && typeFilter !== "all" && item.kind !== typeFilter) return false;
      if (statusFilter !== "all" && item.displayStatus !== statusFilter) return false;
      if (search.trim()) {
        const q = search.trim().toLowerCase();
        if (!item.employeeName.toLowerCase().includes(q) && !item.employeeCode.toLowerCase().includes(q)) return false;
      }
      if (dateFrom && toSortableTime(item.submittedAt) < new Date(`${dateFrom}T00:00:00`).getTime()) return false;
      if (dateTo   && toSortableTime(item.submittedAt) > new Date(`${dateTo}T23:59:59`).getTime())   return false;
      return true;
    });
  }, [allItems, activeTab, typeFilter, statusFilter, search, dateFrom, dateTo]);

  const resetKey = `${activeTab}|${typeFilter}|${statusFilter}|${search}|${dateFrom}|${dateTo}`;

  // ── Selection ── Separation is a multi-stage workflow (approving it means
  // acting on one specific pending stage, not the request as a whole), so it
  // doesn't fit the single-decision bulk approve/reject below — excluded from
  // selection entirely; its rows are actioned individually via the detail page.
  function toggleSelect(key: string) {
    if (allItems.find(i => i.key === key)?.kind === "separation") return;
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }
  function toggleSelectMany(keys: string[], select: boolean) {
    const selectable = keys.filter(k => allItems.find(i => i.key === k)?.kind !== "separation");
    setSelected(prev => {
      const next = new Set(prev);
      selectable.forEach(k => { if (select) next.add(k); else next.delete(k); });
      return next;
    });
  }

  // ── Drawer ── separation has its own detail page with the full stage/
  // clearance/handover UI, so "View" goes there instead of this generic drawer.
  const [drawerItem, setDrawerItem] = useState<ApprovalItem | null>(null);
  function handleView(item: ApprovalItem) {
    if (item.kind === "separation") { router.push(`/dashboard/separation/${item.id}`); return; }
    setDrawerItem(item);
  }

  // ── Single-row approve/reject ──
  const [modal,  setModal]  = useState<ModalState | null>(null);
  const [saving, setSaving] = useState(false);
  const [apiErr, setApiErr] = useState("");

  function handleApproveClick(item: ApprovalItem) { dispatchAction(item, "approve"); }
  function handleRejectClick(item: ApprovalItem)  { dispatchAction(item, "reject"); }

  function dispatchAction(item: ApprovalItem, action: "approve" | "reject") {
    setDrawerItem(null);
    // Separation approval is per-stage (Manager, then HR/Branch Admin) rather
    // than a single yes/no decision, so it's actioned on its own detail page
    // (which already has the full stage/clearance UI) instead of this modal.
    if (item.kind === "separation") {
      router.push(`/dashboard/separation/${item.id}`);
      return;
    }
    if (item.kind === "attendance_correction") {
      if (!window.confirm(
        action === "approve"
          ? `Approve this correction? ${item.employeeName}'s attendance record will be updated immediately.`
          : `Reject this correction request for ${item.employeeName}?`,
      )) return;
      runCorrectionAction(item.id, action);
      return;
    }
    // WFH has no email-template step configured (out of scope for now) — a
    // direct action, same simpler no-modal path as attendance correction,
    // rather than forcing it through ApprovalModal's leave/expense template
    // picker with nothing relevant to select.
    if (item.kind === "wfh") {
      if (!window.confirm(
        action === "approve"
          ? `Approve ${item.employeeName}'s work-from-home request?`
          : `Reject ${item.employeeName}'s work-from-home request?`,
      )) return;
      runWfhAction(item.id, action);
      return;
    }
    if (item.kind === "leave") {
      const r = item.raw as LeaveRequest;
      setModal({
        id: item.id, action, label: `${item.employeeName}'s leave`, kind: "leave",
        employeeName: item.employeeName, employeeEmail: "", autoVars: leaveAutoVars(r),
      });
    } else {
      const r = item.raw as ExpenseRequest;
      setModal({
        id: item.id, action, label: `${item.employeeName}'s expense`, kind: "expense",
        employeeName: item.employeeName, employeeEmail: r.employee_email ?? "",
      });
    }
  }

  async function runCorrectionAction(id: string, action: "approve" | "reject") {
    try {
      await clientApi.patch(API.attendance.correctionReview(id), { action });
      showToast(action === "approve" ? "Correction approved. Attendance record updated." : "Correction rejected.", "success");
      refetchCorrections();
    } catch (err: unknown) {
      const message = (err as { message?: string })?.message ?? "Failed to review correction.";
      showToast(message, "error");
    }
  }

  async function runWfhAction(id: string, action: "approve" | "reject") {
    try {
      await clientApi.post(API.approvals.approveWfh(id), { action });
      showToast(action === "approve" ? "Work from home request approved." : "Work from home request rejected.", "success");
      refetchWfh();
    } catch (err: unknown) {
      const message = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Failed to review request.";
      showToast(message, "error");
    }
  }

  async function handleModalConfirm(
    remarks: string,
    templateName?: string,
    extraContext?: Record<string, string>,
  ) {
    if (!modal) return;
    setSaving(true); setApiErr("");
    try {
      if (modal.kind === "leave") {
        await clientApi.post(API.approvals.approveLeave(modal.id), {
          action: modal.action, remarks, template_name: templateName, extra_context: extraContext,
        });
        refetchLeave();
      } else {
        await clientApi.put(API.expenses.detail(modal.id), {
          status: modal.action === "approve" ? "approved" : "rejected",
          remarks, template_name: templateName, extra_context: extraContext,
        });
        refetchExpense();
      }
      showToast(modal.action === "approve" ? "Request approved." : "Request rejected.", "success");
      setModal(null);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setApiErr(msg || "Action failed. Please try again.");
    } finally { setSaving(false); }
  }

  // ── Bulk approve/reject ──
  const [bulkAction, setBulkAction] = useState<"approve" | "reject" | null>(null);
  const [bulkSaving, setBulkSaving] = useState(false);

  async function handleBulkConfirm(remarks: string) {
    if (!bulkAction) return;
    setBulkSaving(true);
    const targets = allItems.filter(i => selected.has(i.key));
    const results = await Promise.allSettled(targets.map(item => {
      if (item.kind === "leave") {
        return clientApi.post(API.approvals.approveLeave(item.id), { action: bulkAction, remarks });
      }
      if (item.kind === "expense") {
        return clientApi.put(API.expenses.detail(item.id), {
          status: bulkAction === "approve" ? "approved" : "rejected", remarks,
        });
      }
      if (item.kind === "wfh") {
        return clientApi.post(API.approvals.approveWfh(item.id), { action: bulkAction });
      }
      return clientApi.patch(API.attendance.correctionReview(item.id), { action: bulkAction });
    }));

    const succeeded = results.filter(r => r.status === "fulfilled").length;
    const failed = results.length - succeeded;
    const verb = bulkAction === "approve" ? "approved" : "rejected";
    showToast(
      failed === 0
        ? `${succeeded} request${succeeded === 1 ? "" : "s"} ${verb}.`
        : `${succeeded} ${verb}, ${failed} failed — please retry those individually.`,
      failed === 0 ? "success" : "error",
    );

    setSelected(new Set());
    setBulkAction(null);
    setBulkSaving(false);
    refetchAll();
  }

  const initialLoading = (leaveLoading || expenseLoading || correctionLoading || separationLoading || wfhLoading) && allItems.length === 0;
  const refreshing     = leaveLoading || expenseLoading || correctionLoading || separationLoading || wfhLoading;
  const loadError      = leaveError || expenseError || correctionError || separationError || wfhError;

  return (
    <div className="ta-root">
      <SummaryCards pending={counts.pending} leave={counts.leave} expense={counts.expense} correction={counts.correction} loading={initialLoading} />

      <div className="ta-tabs">
        {TYPE_TABS.map(t => (
          <button
            key={t.key}
            className={`ta-tab ${activeTab === t.key ? "active" : ""}`}
            onClick={() => setActiveTab(t.key)}
            suppressHydrationWarning
          >
            <i className={`ti ${t.icon}`} />
            {t.label}
            <span className="ta-tab-count">{tabCounts[t.key]}</span>
          </button>
        ))}
      </div>

      {loadError && (
        <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {loadError}</div>
      )}

      <ApprovalsToolbar
        search={search} onSearch={setSearch}
        status={statusFilter} onStatus={setStatusFilter}
        showTypeFilter={activeTab === "all"}
        type={typeFilter} onType={setTypeFilter}
        dateFrom={dateFrom} onDateFrom={setDateFrom}
        dateTo={dateTo} onDateTo={setDateTo}
        onRefresh={refetchAll}
        refreshing={refreshing}
      />

      <ApprovalsTable
        items={filteredItems}
        loading={initialLoading}
        resetKey={resetKey}
        selected={selected}
        onToggleSelect={toggleSelect}
        onToggleSelectMany={toggleSelectMany}
        onView={handleView}
        onApprove={handleApproveClick}
        onReject={handleRejectClick}
        onBulkApprove={() => setBulkAction("approve")}
        onBulkReject={() => setBulkAction("reject")}
        bulkBusy={bulkSaving}
      />

      <RequestDetailDrawer
        item={drawerItem}
        onClose={() => setDrawerItem(null)}
        onApprove={handleApproveClick}
        onReject={handleRejectClick}
      />

      {apiErr && (
        <div className="alert alert-error" style={{ position: "fixed", bottom: 20, right: 20, zIndex: 1200, maxWidth: 360 }}>
          <i className="ti ti-alert-circle" /> {apiErr}
        </div>
      )}

      {modal && (
        <ApprovalModal
          action={modal.action}
          itemLabel={modal.label}
          employeeName={modal.employeeName}
          employeeEmail={modal.employeeEmail}
          kind={modal.kind}
          entityId={modal.id}
          autoVars={modal.autoVars}
          onConfirm={handleModalConfirm}
          onClose={() => { setModal(null); setApiErr(""); }}
          saving={saving}
        />
      )}

      {bulkAction && (
        <BulkConfirmModal
          action={bulkAction}
          count={selected.size}
          saving={bulkSaving}
          onConfirm={handleBulkConfirm}
          onClose={() => setBulkAction(null)}
        />
      )}
    </div>
  );
}
