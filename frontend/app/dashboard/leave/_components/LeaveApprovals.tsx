"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { LeaveRequest, PaginatedResponse, ReqStatus, STATUS_LABEL, fmtShortDate } from "../_data";
import StatusCell from "./StatusCell";
import LeaveRequestDetailModal from "./LeaveRequestDetailModal";
import StatusMultiSelect, { type StatusOption } from "./StatusMultiSelect";

interface BranchOption     { id: number; branch_name: string }
interface DepartmentOption { id: number; name: string }

const STATUS_OPTIONS: StatusOption[] = (Object.keys(STATUS_LABEL) as ReqStatus[]).map(value => ({
  value,
  label: STATUS_LABEL[value],
}));

interface Props {
  role: string;
}

export default function LeaveApprovals({ role }: Props) {
  const isSystemAdmin = role === "system_admin";
  const canFilterDept  = role === "system_admin" || role === "hr";

  const [branch,     setBranch]     = useState("");
  const [department, setDepartment] = useState("");
  const [statuses,   setStatuses]   = useState<string[]>([]);
  const [actioning, setActioning] = useState<string | null>(null);
  const [rejectId,  setRejectId]  = useState<string | null>(null);
  const [remarks,   setRemarks]   = useState("");
  const [detailRequest, setDetailRequest] = useState<LeaveRequest | null>(null);

  const { data: branchData } = useFetch<BranchOption[] | { results: BranchOption[] }>(
    isSystemAdmin ? `${API.branches.list}?page_size=100` : null
  );
  const branches = Array.isArray(branchData) ? branchData : (branchData?.results ?? []);

  const { data: deptData } = useFetch<DepartmentOption[] | { results: DepartmentOption[] }>(
    canFilterDept ? API.departments.list : null
  );
  const departments = Array.isArray(deptData) ? deptData : (deptData?.results ?? []);

  const params = new URLSearchParams({ scope: "team" });
  if (isSystemAdmin && branch)        params.set("branch", branch);
  if (canFilterDept && department)    params.set("department", department);
  if (statuses.length > 0)            params.set("status", statuses.join(","));

  // No status param → backend infers the pending queue for the caller's role
  // (pending for managers, l2_pending for HR). Selecting terminal statuses
  // (approved/rejected/cancelled) turns this into a history view instead —
  // one filtered table replaces the old separate Pending/History tabs.
  const { data, refetch, loading } = useFetch<PaginatedResponse<LeaveRequest>>(
    `${API.leave.requests}?${params.toString()}`
  );
  const rows = data?.results ?? [];

  async function act(id: string, action: "approve" | "reject", rejectRemarks = "") {
    setActioning(id);
    try {
      await clientApi.post(API.leave.approve(id), { action, remarks: rejectRemarks });
      refetch();
    } finally {
      setActioning(null);
      setRejectId(null);
      setRemarks("");
    }
  }

  return (
    <div className="flex flex-col gap-5">

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        {isSystemAdmin && (
          <select
            value={branch}
            onChange={e => setBranch(e.target.value)}
            suppressHydrationWarning
            className="px-3 py-1.5 text-[13px] rounded-lg border border-[var(--outline-v)] bg-white text-[var(--on-bg)] min-w-[160px]"
          >
            <option value="">All Branches</option>
            {branches.map(b => <option key={b.id} value={b.branch_name}>{b.branch_name}</option>)}
          </select>
        )}
        {canFilterDept && (
          <select
            value={department}
            onChange={e => setDepartment(e.target.value)}
            suppressHydrationWarning
            className="px-3 py-1.5 text-[13px] rounded-lg border border-[var(--outline-v)] bg-white text-[var(--on-bg)] min-w-[160px]"
          >
            <option value="">All Departments</option>
            {departments.map(d => <option key={d.id} value={d.name}>{d.name}</option>)}
          </select>
        )}
        <StatusMultiSelect options={STATUS_OPTIONS} selected={statuses} onChange={setStatuses} />
      </div>

      {/* Table */}
      <div className="card">
        <div className="table-wrap">
          {loading ? (
            <div style={{ padding: "40px 20px", textAlign: "center" }}>
              <i className="ti ti-loader-2" style={{ fontSize: 24, color: "var(--outline-v)" }} />
            </div>
          ) : rows.length === 0 ? (
            <div style={{ padding: "40px 20px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
              {statuses.length === 0 && !branch && !department
                ? "No pending leave requests."
                : "No leave requests match the selected filters."}
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Dept</th>
                  <th>Leave Type</th>
                  <th>From</th>
                  <th>To</th>
                  <th style={{ textAlign: "center" }}>Days</th>
                  <th>Applied</th>
                  <th style={{ textAlign: "center" }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(r => (
                  <tr key={r.id} onClick={() => setDetailRequest(r)} style={{ cursor: "pointer" }}>
                    <td style={{ fontWeight: 600 }}>{r.employee_name}</td>
                    <td style={{ color: "var(--on-variant)", fontSize: 13 }}>{r.employee_dept || "—"}</td>
                    <td>{r.leave_type_display}</td>
                    <td>{fmtShortDate(r.start_date)}</td>
                    <td>{fmtShortDate(r.end_date)}</td>
                    <td style={{ textAlign: "center", fontWeight: 700 }}>{r.total_days}</td>
                    <td style={{ fontSize: 12, color: "var(--on-variant)" }}>{fmtShortDate(r.created_at?.slice(0, 10))}</td>
                    <td style={{ textAlign: "center" }}>
                      <StatusCell request={r} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {detailRequest && (
        <LeaveRequestDetailModal
          requestId={detailRequest.id}
          initialData={detailRequest}
          onClose={() => setDetailRequest(null)}
          onApprove={() => act(detailRequest.id, "approve")}
          onReject={() => { setRejectId(detailRequest.id); setRemarks(""); }}
        />
      )}

      {/* Reject modal */}
      {rejectId && (
        <div className="modal-backdrop" onClick={() => setRejectId(null)}>
          <div className="modal-box" onClick={e => e.stopPropagation()} style={{ maxWidth: 440 }}>
            <div className="modal-header">
              <div className="modal-title">Reject Leave Request</div>
              <button className="modal-close" onClick={() => setRejectId(null)}>
                <i className="ti ti-x" />
              </button>
            </div>
            <div className="modal-body">
              <label className="form-label">Reason for rejection</label>
              <textarea
                className="form-input"
                rows={3}
                placeholder="Provide a reason for the employee…"
                value={remarks}
                onChange={e => setRemarks(e.target.value)}
              />
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setRejectId(null)}>Cancel</button>
              <button
                className="btn btn-filled btn-danger"
                onClick={() => act(rejectId, "reject", remarks)}
                disabled={actioning === rejectId}
              >
                {actioning === rejectId ? <><i className="ti ti-loader-2" /> Rejecting…</> : "Reject"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
