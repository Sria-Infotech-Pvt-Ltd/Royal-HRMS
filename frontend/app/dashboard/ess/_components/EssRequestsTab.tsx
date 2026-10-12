"use client";

// Self-service "My requests" tab, as the Employee Directory reference's "Request register": one list of every
// submission (leave, work from home, expense, attendance correction, HR help) with its code, summary, owner and
// status; selecting a row opens that request's own detail dialog. Same real data and dialogs as the standalone
// My Requests page — only the layout differs.

import { useMemo, useState } from "react";
import clientApi from "@/lib/clientApi";
import { useFetch } from "@/hooks/useFetch";
import { useToast } from "@/components/ToastProvider";
import { API } from "@/lib/api/endpoints";
import type { WorkFromHomeRequest } from "@/types/workFromHome";
import type { HrHelpRequest } from "@/types/hrHelp";
import type { LeaveRequest } from "../../leave/_data";
import LeaveRequestDetailModal from "../../leave/_components/LeaveRequestDetailModal";
import type { Expense } from "../../expenses/_components/ExpenseClaims";
import ExpenseDetailModal from "../../expenses/_components/ExpenseDetailModal";
import MyCorrectionDetailModal from "../../my-requests/_components/MyCorrectionDetailModal";
import HrHelpDetailModal from "../../my-requests/_components/HrHelpDetailModal";
import EmployeeRequestModal from "../../my-requests/_components/EmployeeRequestModal";
import {
  MyCorrectionRequest, MyRequestItem, PaginatedResponse, STATUS_LABEL,
  correctionToMyItem, expenseToMyItem, hrHelpToMyItem, leaveToMyItem, toSortableTime, wfhToMyItem,
} from "../../my-requests/_data";

const MAX_ROWS = 50;

export default function EssRequestsTab() {
  const { showToast } = useToast();
  const [detail, setDetail] = useState<MyRequestItem | null>(null);
  const [showNew, setShowNew] = useState(false);

  const leave = useFetch<PaginatedResponse<LeaveRequest>>(`${API.leave.requests}?page_size=100`);
  const expenses = useFetch<PaginatedResponse<Expense>>(`${API.expenses.list}?page_size=100`);
  const corrections = useFetch<PaginatedResponse<MyCorrectionRequest>>(`${API.attendance.myCorrections}?page_size=100`);
  const wfh = useFetch<PaginatedResponse<WorkFromHomeRequest>>(`${API.workFromHome.requests}?page_size=100`);
  const hrHelp = useFetch<PaginatedResponse<HrHelpRequest>>(`${API.hrHelp.list}?page_size=100`);

  const items = useMemo(() => [
    ...(leave.data?.results ?? []).map(leaveToMyItem),
    ...(expenses.data?.results ?? []).map(expenseToMyItem),
    ...(corrections.data?.results ?? []).map(correctionToMyItem),
    ...(wfh.data?.results ?? []).map(wfhToMyItem),
    ...(hrHelp.data?.results ?? []).map(hrHelpToMyItem),
  ].sort((a, b) => toSortableTime(b.submittedAt) - toSortableTime(a.submittedAt)).slice(0, MAX_ROWS),
  [leave.data, expenses.data, corrections.data, wfh.data, hrHelp.data]);

  const loading = leave.loading || expenses.loading || corrections.loading || wfh.loading || hrHelp.loading;
  const loadError = leave.error || expenses.error || corrections.error || wfh.error || hrHelp.error;

  async function cancelLeave(id: string) {
    try {
      const response = await clientApi.patch<{ message: string }>(API.leave.requestDetail(id));
      showToast(response.data.message, "success");
      leave.refetch();
    } catch (err: unknown) {
      showToast((err as { response?: { data?: { message?: string } } })?.response?.data?.message || "Failed to cancel leave request.", "error");
    } finally {
      setDetail(null);
    }
  }

  return (
    <section className="ess-page">
      <div className="ess-pagehead">
        <div>
          <h2>My requests</h2>
          <p>Track every employee submission and approval step. Select any request to open its full details.</p>
        </div>
        <button className="rvbtn pri" type="button" onClick={() => setShowNew(true)}>New request</button>
      </div>

      {loadError && <div className="alert alert-error">{loadError}</div>}

      <div className="ess-card">
        <h2>Request register</h2>
        <p>Open, completed and returned requests.</p>
        <div className="ess-list">
          {loading && <div className="ess-row"><div><b>Loading requests…</b></div></div>}
          {!loading && items.length === 0 && (
            <div className="ess-row"><div><b>No requests found</b><small>You haven&apos;t submitted any requests yet.</small></div></div>
          )}
          {items.map(item => (
            <button key={item.key} className="ess-row ess-row-link" type="button" aria-label={`Open request ${item.requestCode}`} onClick={() => setDetail(item)}>
              <div>
                <b>{item.requestCode} · {item.title}</b>
                <small>{item.detailSecondary}{item.approver ? ` · Owner: ${item.approver}` : ""}</small>
              </div>
              <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span className={`state${item.displayStatus === "approved" || item.displayStatus === "completed" ? " ok" : ""}`}>
                  {STATUS_LABEL[item.displayStatus].toUpperCase()}
                </span>
                <span className="row-go" aria-hidden="true">›</span>
              </span>
            </button>
          ))}
        </div>
      </div>

      {detail?.kind === "leave" && (
        <LeaveRequestDetailModal
          requestId={detail.id} initialData={detail.raw as LeaveRequest} onClose={() => setDetail(null)}
          onCancelRequest={detail.canCancel ? () => cancelLeave(detail.id) : undefined}
        />
      )}
      {detail?.kind === "expense" && <ExpenseDetailModal initialData={detail.raw as Expense} onClose={() => setDetail(null)} />}
      {detail?.kind === "attendance_correction" && <MyCorrectionDetailModal request={detail.raw as MyCorrectionRequest} onClose={() => setDetail(null)} />}
      {detail?.kind === "hr_help" && <HrHelpDetailModal request={detail.raw as HrHelpRequest} onClose={() => setDetail(null)} />}
      {showNew && (
        <EmployeeRequestModal
          onClose={() => setShowNew(false)}
          onSubmitted={() => { setShowNew(false); showToast("Your request was submitted.", "success"); hrHelp.refetch(); }}
        />
      )}
    </section>
  );
}
