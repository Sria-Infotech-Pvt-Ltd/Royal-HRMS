"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { LeaveRequest, PaginatedResponse, STATUS_BADGE, STATUS_LABEL, fmtShortDate } from "../_data";

type Tab = "pending" | "history";

export default function LeaveApprovals() {
  const currentUser = useCurrentUser();
  const [tab,       setTab]       = useState<Tab>("pending");
  const [actioning, setActioning] = useState<string | null>(null);
  const [rejectId,  setRejectId]  = useState<string | null>(null);
  const [remarks,   setRemarks]   = useState("");

  const { data: pending,  refetch: refetchPending, loading: loadingPending }  =
    useFetch<PaginatedResponse<LeaveRequest>>(API.leave.requests + "?status=pending");

  const { data: l2pending, refetch: refetchL2, loading: loadingL2 } =
    useFetch<PaginatedResponse<LeaveRequest>>(API.leave.requests + "?status=l2_pending");

  const { data: history, refetch: refetchHistory, loading: loadingHistory } =
    useFetch<PaginatedResponse<LeaveRequest>>(API.leave.requests + "?status=approved,rejected,cancelled");

  const allPending = [...(pending?.results ?? []), ...(l2pending?.results ?? [])];
  const rows       = tab === "pending" ? allPending : (history?.results ?? []);
  const loading    = tab === "pending" ? (loadingPending || loadingL2) : loadingHistory;

  function refetchAll() {
    refetchPending();
    refetchL2();
    refetchHistory();
  }

  async function act(id: string, action: "approve" | "reject", rejectRemarks = "") {
    setActioning(id);
    try {
      await clientApi.post(API.leave.approve(id), { action, remarks: rejectRemarks });
      refetchAll();
    } finally {
      setActioning(null);
      setRejectId(null);
      setRemarks("");
    }
  }

  return (
    <div className="flex flex-col gap-5">

      {/* Sub-tabs */}
      <div className="flex gap-2">
        {(["pending", "history"] as const).map(t => (
          <button key={t}
            onClick={() => setTab(t)}
            className={["px-4 py-1.5 rounded-full text-sm font-medium border transition-all",
              tab === t ? "bg-blue-700 text-white border-blue-700" : "bg-white text-gray-500 border-gray-200 hover:border-blue-600 hover:text-blue-600"].join(" ")}>
            {t === "pending" ? "Pending" : "History"}
            {t === "pending" && allPending.length > 0 && (
              <span className={["ml-2 inline-flex items-center justify-center w-5 h-5 rounded-full text-xs font-bold",
                tab === "pending" ? "bg-white text-blue-700" : "bg-amber-100 text-amber-700"].join(" ")}>
                {allPending.length}
              </span>
            )}
          </button>
        ))}
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
              {tab === "pending" ? "No pending leave requests." : "No leave history yet."}
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
                  {tab === "pending" && <th style={{ textAlign: "center" }}>Action</th>}
                </tr>
              </thead>
              <tbody>
                {rows.map(r => (
                  <tr key={r.id}>
                    <td style={{ fontWeight: 600 }}>{r.employee_name}</td>
                    <td style={{ color: "var(--on-variant)", fontSize: 13 }}>{r.employee_dept || "—"}</td>
                    <td>{r.leave_type_display}</td>
                    <td>{fmtShortDate(r.start_date)}</td>
                    <td>{fmtShortDate(r.end_date)}</td>
                    <td style={{ textAlign: "center", fontWeight: 700 }}>{r.total_days}</td>
                    <td style={{ fontSize: 12, color: "var(--on-variant)" }}>{fmtShortDate(r.created_at?.slice(0, 10))}</td>
                    <td style={{ textAlign: "center" }}>
                      <span className={STATUS_BADGE[r.status]}>{STATUS_LABEL[r.status]}</span>
                    </td>
                    {tab === "pending" && (
                      <td style={{ textAlign: "center" }}>
                        {r.employee_name === currentUser?.name ? (
                          <span style={{ fontSize: 11, color: "var(--on-variant)" }} title="You cannot approve your own leave request.">
                            Not applicable
                          </span>
                        ) : (
                          <div style={{ display: "flex", gap: 6, justifyContent: "center" }}>
                            <button
                              className="btn btn-sm btn-success"
                              onClick={() => act(r.id, "approve")}
                              disabled={actioning === r.id}
                              style={{ padding: "4px 10px" }}
                              title="Approve"
                            >
                              {actioning === r.id ? <i className="ti ti-loader-2" /> : <i className="ti ti-check" />}
                            </button>
                            <button
                              className="btn btn-sm btn-danger"
                              onClick={() => { setRejectId(r.id); setRemarks(""); }}
                              disabled={actioning === r.id}
                              style={{ padding: "4px 10px" }}
                              title="Reject"
                            >
                              <i className="ti ti-x" />
                            </button>
                          </div>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

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
