"use client";

import { useEffect, useMemo, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { LeaveRequest } from "../leave/_data";
import LeaveRequestDetailModal from "../leave/_components/LeaveRequestDetailModal";
import type { Expense } from "../expenses/_components/ExpenseClaims";
import ExpenseDetailModal from "../expenses/_components/ExpenseDetailModal";
import MyCorrectionDetailModal from "./_components/MyCorrectionDetailModal";
import {
  DisplayStatus, MyCorrectionRequest, MyRequestItem, MyRequestKind, PaginatedResponse,
  REQUEST_TABS, STATUS_BADGE_CLASS, STATUS_FILTERS, STATUS_LABEL, TYPE_META,
  correctionToMyItem, expenseToMyItem, fmtSubmitted, leaveToMyItem, toSortableTime,
} from "./_data";

type SortKey = "submittedAt" | "lastUpdated" | "status";
const PAGE_SIZE = 10;

function RequestTypeBadge({ kind }: { kind: MyRequestKind }) {
  const meta = TYPE_META[kind];
  return (
    <span className="badge" style={{ background: meta.bg, color: meta.color, gap: 5 }}>
      <i className={`ti ${meta.icon}`} style={{ fontSize: 12 }} /> {meta.label}
    </span>
  );
}

function StatusChip({ status }: { status: DisplayStatus }) {
  return <span className={STATUS_BADGE_CLASS[status]}>{STATUS_LABEL[status]}</span>;
}

interface Props {
  initialTab: "all" | MyRequestKind;
}

export default function MyRequestsClient({ initialTab }: Props) {
  const { showToast } = useToast();

  const [activeTab, setActiveTab] = useState<"all" | MyRequestKind>(initialTab);
  const [search,       setSearch]       = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | DisplayStatus>("all");
  const [dateFrom,     setDateFrom]     = useState("");
  const [dateTo,       setDateTo]       = useState("");
  const [page,         setPage]         = useState(1);
  const [sortKey,      setSortKey]      = useState<SortKey>("submittedAt");
  const [sortDir,      setSortDir]      = useState<"asc" | "desc">("desc");

  const [detailItem, setDetailItem] = useState<MyRequestItem | null>(null);

  const { data: leaveRaw,      loading: leaveLoading,      error: leaveError,      refetch: refetchLeave } =
    useFetch<PaginatedResponse<LeaveRequest>>(`${API.leave.requests}?page_size=100`);
  const { data: expenseRaw,    loading: expenseLoading,    error: expenseError } =
    useFetch<PaginatedResponse<Expense>>(`${API.expenses.list}?page_size=100`);
  const { data: correctionRaw, loading: correctionLoading, error: correctionError } =
    useFetch<PaginatedResponse<MyCorrectionRequest>>(`${API.attendance.myCorrections}?page_size=100`);

  const allItems: MyRequestItem[] = useMemo(() => [
    ...(leaveRaw?.results ?? []).map(leaveToMyItem),
    ...(expenseRaw?.results ?? []).map(expenseToMyItem),
    ...(correctionRaw?.results ?? []).map(correctionToMyItem),
  ], [leaveRaw, expenseRaw, correctionRaw]);

  const tabCounts = useMemo(() => ({
    all: allItems.length,
    leave: allItems.filter(i => i.kind === "leave").length,
    expense: allItems.filter(i => i.kind === "expense").length,
    attendance_correction: allItems.filter(i => i.kind === "attendance_correction").length,
  }), [allItems]);

  const filtered = useMemo(() => {
    return allItems.filter(item => {
      if (activeTab !== "all" && item.kind !== activeTab) return false;
      if (statusFilter !== "all" && item.displayStatus !== statusFilter) return false;
      if (search.trim()) {
        const q = search.trim().toLowerCase();
        if (!item.title.toLowerCase().includes(q) && !item.requestCode.toLowerCase().includes(q)) return false;
      }
      if (dateFrom && toSortableTime(item.submittedAt) < new Date(`${dateFrom}T00:00:00`).getTime()) return false;
      if (dateTo   && toSortableTime(item.submittedAt) > new Date(`${dateTo}T23:59:59`).getTime())   return false;
      return true;
    });
  }, [allItems, activeTab, statusFilter, search, dateFrom, dateTo]);

  const sorted = useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      const cmp = sortKey === "status"
        ? a.displayStatus.localeCompare(b.displayStatus)
        : toSortableTime(a[sortKey]) - toSortableTime(b[sortKey]);
      return sortDir === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [filtered, sortKey, sortDir]);

  useEffect(() => { setPage(1); }, [activeTab, statusFilter, search, dateFrom, dateTo]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const pageItems  = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  function handleSort(key: SortKey) {
    if (key === sortKey) setSortDir(d => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("desc"); }
  }

  function sortIcon(key: SortKey) {
    if (key !== sortKey) return "ti-arrows-sort";
    return sortDir === "asc" ? "ti-arrow-up" : "ti-arrow-down";
  }

  async function cancelLeave(id: string) {
    try {
      const res = await clientApi.patch<{ message: string }>(API.leave.requestDetail(id));
      showToast(res.data.message, "success");
      refetchLeave();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      showToast(msg || "Failed to cancel leave request.", "error");
    } finally {
      setDetailItem(null);
    }
  }

  const loading = leaveLoading || expenseLoading || correctionLoading;
  const loadError = leaveError || expenseError || correctionError;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">My Requests</div>
          <div className="page-sub">Track every leave, expense, and attendance correction request you&rsquo;ve submitted</div>
        </div>
      </div>

      <div className="tabs">
        {REQUEST_TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            suppressHydrationWarning
            className={`tab flex items-center gap-[7px] ${activeTab === t.key ? "active" : ""}`}
          >
            <i className={`ti ${t.icon} text-[15px]`} />
            {t.label}
            <span className="badge badge-neutral" style={{ fontSize: 10 }}>{tabCounts[t.key]}</span>
          </button>
        ))}
      </div>

      {loadError && (
        <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {loadError}</div>
      )}

      {/* Toolbar */}
      <div className="filter-bar">
        <div className="search-bar">
          <i className="ti ti-search" />
          <input
            type="text"
            placeholder="Search by title or request ID…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            suppressHydrationWarning
          />
        </div>
        <select
          className="field-input field-select"
          style={{ width: 160 }}
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value as "all" | DisplayStatus)}
          suppressHydrationWarning
        >
          {STATUS_FILTERS.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
        </select>
        <input
          type="date"
          className="field-input"
          style={{ width: 150 }}
          value={dateFrom}
          onChange={e => setDateFrom(e.target.value)}
          title="Submitted from"
          suppressHydrationWarning
        />
        <span style={{ fontSize: 12, color: "var(--on-variant)" }}>to</span>
        <input
          type="date"
          className="field-input"
          style={{ width: 150 }}
          value={dateTo}
          onChange={e => setDateTo(e.target.value)}
          title="Submitted to"
          suppressHydrationWarning
        />
      </div>

      <div className="card">
        <div className="table-wrap">
          {loading && allItems.length === 0 ? (
            <div style={{ padding: "60px 20px", textAlign: "center" }}>
              <i className="ti ti-loader-2 spin" style={{ fontSize: 24, color: "var(--primary)" }} />
            </div>
          ) : sorted.length === 0 ? (
            <div className="empty-state">
              <i className="ti ti-inbox" />
              <h3>No requests found</h3>
              <p>{allItems.length === 0 ? "You haven't submitted any requests yet." : "No requests match the selected filters."}</p>
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Request ID</th>
                  <th>Request Type</th>
                  <th>Title</th>
                  <th style={{ cursor: "pointer" }} onClick={() => handleSort("submittedAt")}>
                    Submitted Date <i className={`ti ${sortIcon("submittedAt")}`} />
                  </th>
                  <th style={{ cursor: "pointer" }} onClick={() => handleSort("status")}>
                    Status <i className={`ti ${sortIcon("status")}`} />
                  </th>
                  <th>Approver</th>
                  <th style={{ cursor: "pointer" }} onClick={() => handleSort("lastUpdated")}>
                    Last Updated <i className={`ti ${sortIcon("lastUpdated")}`} />
                  </th>
                  <th style={{ textAlign: "right" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {pageItems.map(item => (
                  <tr key={item.key} onClick={() => setDetailItem(item)} style={{ cursor: "pointer" }}>
                    <td className="font-mono text-xs">{item.requestCode}</td>
                    <td><RequestTypeBadge kind={item.kind} /></td>
                    <td>
                      <div style={{ fontWeight: 500 }}>{item.title}</div>
                      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{item.detailSecondary}</div>
                    </td>
                    <td>{fmtSubmitted(item.submittedAt)}</td>
                    <td><StatusChip status={item.displayStatus} /></td>
                    <td style={{ color: "var(--on-variant)" }}>{item.approver}</td>
                    <td>{fmtSubmitted(item.lastUpdated)}</td>
                    <td style={{ textAlign: "right" }} onClick={e => e.stopPropagation()}>
                      <button className="btn btn-ghost btn-sm" onClick={() => setDetailItem(item)} suppressHydrationWarning>
                        <i className="ti ti-eye" /> View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {sorted.length > 0 && totalPages > 1 && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 20px", borderTop: "1px solid var(--outline-v)" }}>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>
              Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, sorted.length)} of {sorted.length}
            </span>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))}>
                <i className="ti ti-chevron-left" /> Prev
              </button>
              <button className="btn btn-ghost btn-sm" disabled={page >= totalPages} onClick={() => setPage(p => Math.min(totalPages, p + 1))}>
                Next <i className="ti ti-chevron-right" />
              </button>
            </div>
          </div>
        )}
      </div>

      {detailItem?.kind === "leave" && (
        <LeaveRequestDetailModal
          requestId={detailItem.id}
          initialData={detailItem.raw as LeaveRequest}
          onClose={() => setDetailItem(null)}
          onCancelRequest={detailItem.canCancel ? () => cancelLeave(detailItem.id) : undefined}
        />
      )}

      {detailItem?.kind === "expense" && (
        <ExpenseDetailModal
          initialData={detailItem.raw as Expense}
          onClose={() => setDetailItem(null)}
        />
      )}

      {detailItem?.kind === "attendance_correction" && (
        <MyCorrectionDetailModal
          request={detailItem.raw as MyCorrectionRequest}
          onClose={() => setDetailItem(null)}
        />
      )}
    </div>
  );
}
