"use client";

// ESS "Requests" tab — a simple register of every request the employee has
// ever submitted (leave, expense, attendance correction, WFH, HR help),
// matching the reference layout: one plain list, no search/filter/sort/
// pagination toolbar. Reuses the exact same real data/mapping helpers and
// detail modals as the richer /dashboard/my-requests admin-style page
// (app/dashboard/my-requests/_client.tsx), which keeps its own full
// search/filter/sort/pagination UI untouched for that separate screen.

import { useMemo, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { LeaveRequest } from "../../leave/_data";
import LeaveRequestDetailModal from "../../leave/_components/LeaveRequestDetailModal";
import type { Expense } from "../../expenses/_components/ExpenseClaims";
import ExpenseDetailModal from "../../expenses/_components/ExpenseDetailModal";
import MyCorrectionDetailModal from "../../my-requests/_components/MyCorrectionDetailModal";
import HrHelpDetailModal from "../../my-requests/_components/HrHelpDetailModal";
import EmployeeRequestModal from "../../my-requests/_components/EmployeeRequestModal";
import type { WorkFromHomeRequest } from "@/types/workFromHome";
import type { HrHelpRequest } from "@/types/hrHelp";
import {
  MyCorrectionRequest, MyRequestItem, PaginatedResponse,
  STATUS_BADGE_CLASS, STATUS_LABEL,
  correctionToMyItem, expenseToMyItem, hrHelpToMyItem, leaveToMyItem, toSortableTime, wfhToMyItem,
} from "../../my-requests/_data";

export default function MyRequestsSummaryTab() {
  const { showToast } = useToast();
  const [detailItem, setDetailItem] = useState<MyRequestItem | null>(null);
  const [showNewRequest, setShowNewRequest] = useState(false);

  const { data: leaveRaw } = useFetch<PaginatedResponse<LeaveRequest>>(`${API.leave.requests}?page_size=100`);
  const { data: expenseRaw } = useFetch<PaginatedResponse<Expense>>(`${API.expenses.list}?page_size=100`);
  const { data: correctionRaw } = useFetch<PaginatedResponse<MyCorrectionRequest>>(`${API.attendance.myCorrections}?page_size=100`);
  const { data: wfhRaw } = useFetch<PaginatedResponse<WorkFromHomeRequest>>(`${API.workFromHome.requests}?page_size=100`);
  const { data: hrHelpRaw, refetch: refetchHrHelp } = useFetch<PaginatedResponse<HrHelpRequest>>(`${API.hrHelp.list}?page_size=100`);

  const items: MyRequestItem[] = useMemo(() => [
    ...(leaveRaw?.results ?? []).map(leaveToMyItem),
    ...(expenseRaw?.results ?? []).map(expenseToMyItem),
    ...(correctionRaw?.results ?? []).map(correctionToMyItem),
    ...(wfhRaw?.results ?? []).map(wfhToMyItem),
    ...(hrHelpRaw?.results ?? []).map(hrHelpToMyItem),
  ].sort((a, b) => toSortableTime(b.submittedAt) - toSortableTime(a.submittedAt)), [leaveRaw, expenseRaw, correctionRaw, wfhRaw, hrHelpRaw]);

  async function cancelLeave(id: string) {
    try {
      const res = await clientApi.patch<{ message: string }>(API.leave.requestDetail(id));
      showToast(res.data.message, "success");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      showToast(msg || "Failed to cancel leave request.", "error");
    } finally {
      setDetailItem(null);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">My requests</div>
          <div className="page-sub">Track every employee submission and approval step. Select any request to open its full details.</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-filled" onClick={() => setShowNewRequest(true)}>
            New request
          </button>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">Request register</div>
            <div className="page-sub" style={{ marginTop: 2 }}>Open, completed and returned requests.</div>
          </div>
        </div>
        {items.length === 0 ? (
          <div style={{ padding: "4px 24px 20px" }}>
            <div style={{ fontWeight: 600, fontSize: 14 }}>No requests yet</div>
            <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 2 }}>
              Anything you submit will appear here.
            </div>
          </div>
        ) : (
          <div style={{ padding: "4px 24px 8px" }}>
            {items.map((item, idx) => (
              <div
                key={item.key}
                onClick={() => setDetailItem(item)}
                style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "14px 0", cursor: "pointer", gap: 12,
                  borderTop: idx === 0 ? "none" : "1px solid var(--outline-v)",
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{item.requestCode} · {item.title}</div>
                  <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
                    {item.detailSecondary} · Owner: {item.approver !== "—" ? item.approver : "Reporting Manager"}
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
                  <i className="ti ti-chevron-right" style={{ color: "var(--primary)" }} />
                  <span className={STATUS_BADGE_CLASS[item.displayStatus]}>{STATUS_LABEL[item.displayStatus]}</span>
                </div>
              </div>
            ))}
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

      {detailItem?.kind === "hr_help" && (
        <HrHelpDetailModal
          request={detailItem.raw as HrHelpRequest}
          onClose={() => setDetailItem(null)}
        />
      )}

      {showNewRequest && (
        <EmployeeRequestModal
          onClose={() => setShowNewRequest(false)}
          onSubmitted={() => {
            setShowNewRequest(false);
            showToast("Your request was submitted.", "success");
            refetchHrHelp();
          }}
        />
      )}
    </div>
  );
}
