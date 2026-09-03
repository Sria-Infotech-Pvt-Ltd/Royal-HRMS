"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { usePermission } from "@/hooks/usePermission";
import { useDepartmentOptions } from "@/hooks/useDepartmentOptions";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { getEffectiveBranch, isUnrestrictedUser } from "@/lib/auth";
import { useToast } from "@/components/ToastProvider";
import BranchFilterSelect from "@/components/BranchFilterSelect";
import type { CorrectionReviewAction, CorrectionStatus, PaginatedCorrections, PunchType } from "@/types/attendance";

interface BranchOption { id: number; branch_name: string }

const PUNCH_TYPE_LABEL: Record<PunchType, string> = {
  IN:   "Clock In",
  OUT:  "Clock Out",
  BOTH: "Both IN & OUT",
};

const STATUS_BADGE: Record<CorrectionStatus, string> = {
  pending:    "badge badge-warn",
  l2_pending: "badge badge-info",
  approved:   "badge badge-success",
  rejected:   "badge badge-error",
};

const STATUS_LABEL: Record<CorrectionStatus, string> = {
  pending:    "Pending (Manager)",
  l2_pending: "Pending (HR)",
  approved:   "Approved",
  rejected:   "Rejected",
};

const STATUS_OPTIONS: { value: CorrectionStatus | ""; label: string }[] = [
  { value: "",           label: "All"              },
  { value: "pending",    label: "Pending — Manager" },
  { value: "l2_pending", label: "Pending — HR"      },
  { value: "approved",   label: "Approved"          },
  { value: "rejected",   label: "Rejected"          },
];

function toQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.append(key, String(value));
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}

export default function CorrectionsTab() {
  const { showToast } = useToast();
  const user            = useCurrentUser();
  const unrestricted    = isUnrestrictedUser(user);
  const effectiveBranch = getEffectiveBranch(user);
  const canReview       = usePermission("attendance.create");

  const [branchInput, setBranchInput] = useState("");
  const [department, setDepartment] = useState("");
  const [status, setStatus]         = useState<CorrectionStatus | "">("pending");
  const [page, setPage]             = useState(1);
  const [reviewingId, setReviewingId] = useState<string | null>(null);

  const branch = unrestricted ? branchInput : effectiveBranch;

  const { data: branchData } = useFetch<BranchOption[] | { results: BranchOption[] }>(
    unrestricted ? `${API.branches.list}?page_size=100` : null
  );
  const branches    = Array.isArray(branchData) ? branchData : (branchData?.results ?? []);
  const departments = useDepartmentOptions(unrestricted, effectiveBranch);

  const listUrl = user
    ? `${API.attendance.corrections}${toQuery({ branch, department, status, page, page_size: 20 })}`
    : null;
  const { data, loading, error, refetch } = useFetch<PaginatedCorrections>(listUrl);
  const rows = data?.results ?? [];

  async function handleReview(id: string, action: CorrectionReviewAction) {
    setReviewingId(id);
    try {
      await clientApi.patch(API.attendance.correctionReview(id), { action });
      showToast(action === "approve" ? "Correction approved. Attendance record updated." : "Correction rejected.", "success");
      refetch();
    } catch (err: unknown) {
      const message = (err as { message?: string })?.message ?? "Failed to review correction.";
      showToast(message, "error");
    } finally {
      setReviewingId(null);
    }
  }

  return (
    <>
      <div className="filter-bar" style={{ marginBottom: 14 }}>
        <BranchFilterSelect
          branches={branches}
          value={branchInput}
          onChange={value => { setBranchInput(value); setPage(1); }}
          locked={!unrestricted}
          lockedBranchName={effectiveBranch}
        />
        <select className="field-input field-select" style={{ width: 180 }} value={department} onChange={e => { setDepartment(e.target.value); setPage(1); }}>
          <option value="">All Departments</option>
          {departments.map(d => <option key={d} value={d}>{d}</option>)}
        </select>
        <select
          className="field-input field-select"
          style={{ width: 160 }}
          value={status}
          onChange={e => { setStatus(e.target.value as CorrectionStatus | ""); setPage(1); }}
        >
          {STATUS_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
        </select>
      </div>

      {error && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {error}</div>}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Employee ID</th>
                <th>Name</th>
                <th>Department</th>
                <th>Branch</th>
                <th>Date</th>
                <th>Punch Type</th>
                <th>Requested In</th>
                <th>Requested Out</th>
                <th>Reason</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={11} style={{ textAlign: "center", padding: 24, color: "var(--on-variant)" }}>Loading…</td></tr>
              )}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={11} style={{ textAlign: "center", padding: 24, color: "var(--on-variant)" }}>No correction requests found.</td></tr>
              )}
              {rows.map(r => (
                <tr key={r.id}>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12 }}>{r.employee_id}</td>
                  <td>{r.name}</td>
                  <td>{r.department}</td>
                  <td>{r.branch}</td>
                  <td>{r.date}</td>
                  <td>{PUNCH_TYPE_LABEL[r.punch_type]}</td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12 }}>{r.requested_in ?? "—"}</td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12 }}>{r.requested_out ?? "—"}</td>
                  <td style={{ maxWidth: 220, fontSize: 12, color: "var(--on-variant)" }}>{r.reason}</td>
                  <td>
                    <span className={STATUS_BADGE[r.status]}>{STATUS_LABEL[r.status]}</span>
                    {(r.status === "pending" || r.status === "l2_pending") && (
                      <div style={{ fontSize: 10, color: "var(--on-variant)", marginTop: 2 }}>
                        {r.status === "pending"
                          ? (r.l1_approver_name ? `Awaiting ${r.l1_approver_name}` : "Awaiting manager")
                          : (r.l2_approver_name ? `Awaiting ${r.l2_approver_name}` : "Awaiting HR")}
                      </div>
                    )}
                  </td>
                  <td>
                    {canReview && r.can_action ? (
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <button
                          className="btn btn-outline btn-sm"
                          style={{ padding: "3px 10px", fontSize: 11, color: "var(--success)" }}
                          disabled={reviewingId === r.id}
                          onClick={() => handleReview(r.id, "approve")}
                        >
                          <i className="ti ti-check" /> Approve
                        </button>
                        <button
                          className="btn btn-outline btn-sm"
                          style={{ padding: "3px 10px", fontSize: 11, color: "var(--error)" }}
                          disabled={reviewingId === r.id}
                          onClick={() => handleReview(r.id, "reject")}
                        >
                          <i className="ti ti-x" /> Reject
                        </button>
                      </div>
                    ) : (
                      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
                        {r.l1_status && <div>L1: {r.l1_approver_name} — {r.l1_status}</div>}
                        {r.l2_status && <div>L2: {r.l2_approver_name} — {r.l2_status}</div>}
                        {!r.l1_status && !r.l2_status && r.reviewed_by && <div>{r.reviewed_by}</div>}
                        {r.reviewed_at && <div>{r.reviewed_at}</div>}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {data && data.total_pages > 1 && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 20px", borderTop: "1px solid var(--outline-v)" }}>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Page {data.page} of {data.total_pages}</span>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(p => Math.max(p - 1, 1))}>
                <i className="ti ti-chevron-left" /> Prev
              </button>
              <button className="btn btn-ghost btn-sm" disabled={page >= data.total_pages} onClick={() => setPage(p => Math.min(p + 1, data.total_pages))}>
                Next <i className="ti ti-chevron-right" />
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
