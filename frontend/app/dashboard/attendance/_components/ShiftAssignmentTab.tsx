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
import Modal from "@/components/Modal";
import ShiftMasterCard from "./ShiftMasterCard";

interface ShiftOption { id: string; name: string; policy_code: string }
interface ShiftPage { results: ShiftOption[] }

interface AssignmentRow {
  employee_id: string;
  employee_name: string;
  department: string;
  branch: string;
  shift_id: string | null;
  shift_name: string | null;
  effective_from: string | null;
  effective_to: string | null;
  status: "Assigned" | "Not Assigned";
}
interface PaginatedAssignments {
  count: number; page: number; page_size: number; total_pages: number;
  results: AssignmentRow[];
}

const STATUS_OPTIONS = [
  { value: "",           label: "All" },
  { value: "assigned",   label: "Assigned" },
  { value: "unassigned", label: "Not Assigned (Global Default)" },
];

function toQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.append(key, String(value));
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}

export default function ShiftAssignmentTab() {
  const { showToast } = useToast();
  const user            = useCurrentUser();
  const unrestricted    = isUnrestrictedUser(user);
  const effectiveBranch = getEffectiveBranch(user);
  const canAssign        = usePermission("attendance.create");

  const [branchInput, setBranchInput] = useState("");
  const [department, setDepartment]   = useState("");
  const [shift, setShift]             = useState("");
  const [status, setStatus]           = useState("");
  const [page, setPage]               = useState(1);

  const [assignTarget, setAssignTarget] = useState<AssignmentRow | null>(null);
  const [assignShift, setAssignShift] = useState("");
  const [assignDate, setAssignDate] = useState("");
  const [assigning, setAssigning] = useState(false);
  const [assignErr, setAssignErr] = useState<string | null>(null);

  const [showBulk, setShowBulk] = useState(false);
  const [bulkShift, setBulkShift] = useState("");
  const [bulkDate, setBulkDate] = useState("");
  const [bulkBranch, setBulkBranch] = useState("");
  const [bulkDept, setBulkDept] = useState("");
  const [bulking, setBulking] = useState(false);
  const [bulkErr, setBulkErr] = useState<string | null>(null);

  const branch = unrestricted ? branchInput : effectiveBranch;

  const { data: branchData } = useFetch<{ id: number; branch_name: string }[] | { results: { id: number; branch_name: string }[] }>(
    unrestricted ? `${API.branches.list}?page_size=100` : null
  );
  const branches    = Array.isArray(branchData) ? branchData : (branchData?.results ?? []);
  const departments = useDepartmentOptions(unrestricted, effectiveBranch);

  const { data: shiftData } = useFetch<ShiftPage>(`${API.attendance.workingHoursPolicies}?page_size=50&is_active=true`);
  const shifts = shiftData?.results ?? [];

  const listUrl = user
    ? `${API.attendance.shiftAssignments}${toQuery({ branch, department, shift, status, page, page_size: 20 })}`
    : null;
  const { data, loading, error, refetch } = useFetch<PaginatedAssignments>(listUrl);
  const rows = data?.results ?? [];

  function openAssign(row: AssignmentRow) {
    setAssignTarget(row);
    setAssignShift(row.shift_id ?? "");
    setAssignDate(new Date().toISOString().slice(0, 10));
    setAssignErr(null);
  }

  async function handleAssign() {
    if (!assignTarget) return;
    setAssigning(true);
    setAssignErr(null);
    try {
      await clientApi.post(API.attendance.shiftAssignments, {
        employee_id: assignTarget.employee_id,
        shift: assignShift,
        effective_from: assignDate,
      });
      showToast(`Shift assigned to ${assignTarget.employee_name}.`, "success");
      setAssignTarget(null);
      refetch();
    } catch (err: unknown) {
      const e = err as { message?: string };
      setAssignErr(e.message ?? "Failed to assign shift.");
    } finally {
      setAssigning(false);
    }
  }

  async function handleBulkAssign() {
    setBulking(true);
    setBulkErr(null);
    try {
      const res = await clientApi.post<{ data: { count: number } }>(API.attendance.shiftAssignmentsBulk, {
        shift: bulkShift,
        effective_from: bulkDate,
        branch: bulkBranch,
        department: bulkDept,
      });
      const count = res.data?.data?.count ?? 0;
      showToast(`Shift assigned to ${count} employee(s).`, "success");
      setShowBulk(false);
      refetch();
    } catch (err: unknown) {
      const e = err as { message?: string };
      setBulkErr(e.message ?? "Bulk assignment failed.");
    } finally {
      setBulking(false);
    }
  }

  return (
    <>
      {canAssign && (
        <div style={{ marginBottom: 20 }}>
          <ShiftMasterCard />
        </div>
      )}

      <div className="filter-bar" style={{ marginBottom: 14, justifyContent: "space-between" }}>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <BranchFilterSelect
            branches={branches}
            value={branchInput}
            onChange={value => { setBranchInput(value); setPage(1); }}
            locked={!unrestricted}
            lockedBranchName={effectiveBranch}
          />
          <select className="field-input" style={{ width: 180 }} value={department} onChange={e => { setDepartment(e.target.value); setPage(1); }}>
            <option value="">All Departments</option>
            {departments.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
          <select className="field-input" style={{ width: 180 }} value={shift} onChange={e => { setShift(e.target.value); setPage(1); }}>
            <option value="">All Shifts</option>
            {shifts.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <select className="field-input" style={{ width: 220 }} value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}>
            {STATUS_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
          </select>
        </div>
        {canAssign && (
          <button className="btn btn-filled btn-sm" onClick={() => { setShowBulk(true); setBulkErr(null); setBulkDate(new Date().toISOString().slice(0, 10)); }} suppressHydrationWarning>
            <i className="ti ti-users" /> Bulk Assign
          </button>
        )}
      </div>

      {error && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {error}</div>}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Employee ID</th>
                <th>Employee Name</th>
                <th>Department</th>
                <th>Branch</th>
                <th>Shift</th>
                <th>Effective From</th>
                <th>Effective To</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={9} style={{ textAlign: "center", padding: 24, color: "var(--on-variant)" }}>Loading…</td></tr>
              )}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={9} style={{ textAlign: "center", padding: 24, color: "var(--on-variant)" }}>No employees found.</td></tr>
              )}
              {rows.map(r => (
                <tr key={r.employee_id}>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12 }}>{r.employee_id}</td>
                  <td>{r.employee_name}</td>
                  <td>{r.department}</td>
                  <td>{r.branch}</td>
                  <td>{r.shift_name ?? "General / Default"}</td>
                  <td>{r.effective_from ?? "—"}</td>
                  <td>{r.effective_to ?? "-"}</td>
                  <td>
                    <span className={r.status === "Assigned" ? "badge badge-success" : "badge badge-neutral"}>
                      {r.status}
                    </span>
                  </td>
                  <td>
                    {canAssign && (
                      <button className="btn btn-outline btn-sm" style={{ padding: "3px 10px", fontSize: 11 }} onClick={() => openAssign(r)}>
                        <i className="ti ti-edit" /> {r.status === "Assigned" ? "Change" : "Assign"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {data && data.total_pages > 1 && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 20px", borderTop: "1px solid var(--outline-v)" }}>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Page {data.page} of {data.total_pages} · {data.count} employees</span>
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

      {/* ── Single assign modal ──────────────────────────────────────────── */}
      {assignTarget && (
        <Modal
          title={<><i className="ti ti-clock-cog" /> Assign Shift</>}
          onClose={() => setAssignTarget(null)}
          closeDisabled={assigning}
          maxWidth="min(440px, 94vw)"
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setAssignTarget(null)} disabled={assigning} suppressHydrationWarning>Cancel</button>
              <button className="btn btn-filled" onClick={handleAssign} disabled={assigning || !assignShift || !assignDate} suppressHydrationWarning>
                {assigning ? "Assigning…" : "Assign"}
              </button>
            </>
          }
        >
          {assignErr && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {assignErr}</div>}
          <p style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 12 }}>
            {assignTarget.employee_name} ({assignTarget.employee_id})
            {assignTarget.status === "Assigned" && (
              <> — currently <strong>{assignTarget.shift_name}</strong>, effective {assignTarget.effective_from}</>
            )}
            {assignTarget.status === "Not Assigned" && (
              <> — currently on the <strong>global default</strong> schedule</>
            )}
          </p>
          <div className="field-group">
            <label className="field-label">Shift</label>
            <select className="field-input" value={assignShift} onChange={e => setAssignShift(e.target.value)}>
              <option value="">Select shift…</option>
              {shifts.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div className="field-group">
            <label className="field-label">Effective From</label>
            <input type="date" className="field-input" value={assignDate} onChange={e => setAssignDate(e.target.value)} />
          </div>
          <p style={{ fontSize: 11, color: "var(--on-variant)" }}>
            Past attendance is never affected — this shift applies from the effective date forward only.
          </p>
        </Modal>
      )}

      {/* ── Bulk assign modal ────────────────────────────────────────────── */}
      {showBulk && (
        <Modal
          title={<><i className="ti ti-users" /> Bulk Assign Shift</>}
          onClose={() => setShowBulk(false)}
          closeDisabled={bulking}
          maxWidth="min(480px, 94vw)"
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setShowBulk(false)} disabled={bulking} suppressHydrationWarning>Cancel</button>
              <button
                className="btn btn-filled"
                onClick={handleBulkAssign}
                disabled={bulking || !bulkShift || !bulkDate || (!bulkBranch && !bulkDept && unrestricted)}
                suppressHydrationWarning
              >
                {bulking ? "Assigning…" : "Assign to Matching Employees"}
              </button>
            </>
          }
        >
          {bulkErr && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {bulkErr}</div>}
          <p style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 12 }}>
            Applies to every active employee matching the filters below — resolved on the
            server, so no employee list needs to load into the browser first. No business
            rule auto-selects employees by branch/department/role — you choose exactly who
            this applies to.
          </p>
          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Branch</label>
              <BranchFilterSelect
                branches={branches}
                value={unrestricted ? bulkBranch : effectiveBranch}
                onChange={v => setBulkBranch(v)}
                locked={!unrestricted}
                lockedBranchName={effectiveBranch}
              />
            </div>
            <div className="field-group">
              <label className="field-label">Department</label>
              <select className="field-input" value={bulkDept} onChange={e => setBulkDept(e.target.value)}>
                <option value="">All Departments</option>
                {departments.map(d => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
          </div>
          <div className="field-group">
            <label className="field-label">Shift</label>
            <select className="field-input" value={bulkShift} onChange={e => setBulkShift(e.target.value)}>
              <option value="">Select shift…</option>
              {shifts.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div className="field-group">
            <label className="field-label">Effective From</label>
            <input type="date" className="field-input" value={bulkDate} onChange={e => setBulkDate(e.target.value)} />
          </div>
        </Modal>
      )}
    </>
  );
}
