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
import { MONO, Notice, Pager, Pill, SectionCard, TableStates, PersonCell } from "./SectionCard";
import { PALETTE, tint } from "./attendancePalette";
import type { CorrectionReviewAction, CorrectionStatus, PaginatedCorrections, PunchType } from "@/types/attendance";

interface BranchOption { id: number; branch_name: string }

const PUNCH_TYPE_LABEL: Record<PunchType, string> = {
  IN:   "Clock In",
  OUT:  "Clock Out",
  BOTH: "Both IN & OUT",
};

const STATUS_COLOUR: Record<CorrectionStatus, string> = {
  pending:    PALETTE.late,
  l2_pending: PALETTE.half_day,
  approved:   PALETTE.present,
  rejected:   PALETTE.absent,
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

  const filters = (
    <>
      <BranchFilterSelect branches={branches} value={branchInput} onChange={value => { setBranchInput(value); setPage(1); }} locked={!unrestricted} lockedBranchName={effectiveBranch} />
      <select className="field-input field-select" style={{ width: 180 }} value={department} onChange={e => { setDepartment(e.target.value); setPage(1); }}>
        <option value="">All Org Units</option>
        {departments.map(d => <option key={d} value={d}>{d}</option>)}
      </select>
      <div role="group" aria-label="Status" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {STATUS_OPTIONS.map(option => {
          const selected = status === option.value;
          const colour = option.value ? STATUS_COLOUR[option.value] : PALETTE.brand;
          return (
            <button
              key={option.value || "all"} type="button" aria-pressed={selected} onClick={() => { setStatus(option.value); setPage(1); }}
              style={{ padding: "6px 13px", borderRadius: 999, fontSize: 12.5, fontWeight: 700, cursor: "pointer", transition: "all .15s ease", border: `1.5px solid ${selected ? colour : "var(--outline-v)"}`, background: selected ? tint(colour, 0.12) : "var(--surface)", color: selected ? colour : "var(--on-variant)" }}
            >{option.label}</button>
          );
        })}
      </div>
    </>
  );

  return (
    <SectionCard icon="ti-file-text" colour={PALETTE.brand} title="Corrections" count={data?.count ?? null} filters={filters} subtitle="Requests from employees to fix a missed or wrong punch. Approve or reject each one.">
      {error && <Notice tone="error" icon="ti-alert-circle">{error}</Notice>}
      <div className="table-wrap" style={{ marginTop: error ? 14 : 0 }}>
        <table>
          <thead>
            <tr><th>Employee</th><th>Department</th><th>Date</th><th>Punch Type</th><th>Requested In</th><th>Requested Out</th><th>Reason</th><th>Status</th><th>Actions</th></tr>
          </thead>
          <tbody>
            <TableStates columns={9} loading={loading} empty={rows.length === 0} icon="ti-file-check" title="No correction requests found." hint="Try another status above to see the rest." />
            {rows.map(r => (
              <tr key={r.id}>
                <td><PersonCell name={r.name} employeeId={r.employee_id} /></td>
                <td>
                  <div style={{ fontSize: 13 }}>{r.department}</div>
                  <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{r.branch}</div>
                </td>
                <td>{r.date}</td>
                <td><Pill colour={PALETTE.half_day}>{PUNCH_TYPE_LABEL[r.punch_type]}</Pill></td>
                <td style={{ ...MONO, fontWeight: 700 }}>{r.requested_in ?? "—"}</td>
                <td style={{ ...MONO, fontWeight: 700 }}>{r.requested_out ?? "—"}</td>
                <td style={{ maxWidth: 220, fontSize: 12, color: "var(--on-variant)" }}>{r.reason}</td>
                <td>
                  <Pill colour={STATUS_COLOUR[r.status]}>{STATUS_LABEL[r.status]}</Pill>
                  {(r.status === "pending" || r.status === "l2_pending") && (
                    <div style={{ fontSize: 10.5, color: "var(--on-variant)", marginTop: 4 }}>
                      {r.status === "pending"
                        ? (r.l1_approver_name ? `Awaiting ${r.l1_approver_name}` : "Awaiting manager")
                        : (r.l2_approver_name ? `Awaiting ${r.l2_approver_name}` : "Awaiting HR")}
                    </div>
                  )}
                </td>
                <td>
                  {canReview && r.can_action ? (
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <button className="btn btn-outline btn-sm" style={{ padding: "3px 10px", fontSize: 11, color: PALETTE.present }} disabled={reviewingId === r.id} onClick={() => handleReview(r.id, "approve")}><i className="ti ti-check" /> Approve</button>
                      <button className="btn btn-outline btn-sm" style={{ padding: "3px 10px", fontSize: 11, color: PALETTE.absent }} disabled={reviewingId === r.id} onClick={() => handleReview(r.id, "reject")}><i className="ti ti-x" /> Reject</button>
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
      <Pager data={data} page={page} onPage={setPage} />
    </SectionCard>
  );
}
