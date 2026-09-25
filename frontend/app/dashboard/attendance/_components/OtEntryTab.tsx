"use client";

import { useState } from "react";
import SearchableSelect from "@/components/SearchableSelect";
import { useFetch } from "@/hooks/useFetch";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { usePermission } from "@/hooks/usePermission";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { getEffectiveBranch, isUnrestrictedUser } from "@/lib/auth";
import { useToast } from "@/components/ToastProvider";
import BranchFilterSelect from "@/components/BranchFilterSelect";
import type { OvertimeCreatePayload, PaginatedOvertime } from "@/types/attendance";

interface PickerEmployee {
  employee_id: string;
  full_name:   string;
}

interface BranchOption { id: number; branch_name: string }

const EMPTY_FORM: OvertimeCreatePayload = {
  employee_id: "",
  date:        new Date().toISOString().slice(0, 10),
  ot_type:     "regular",
  ot_start:    "18:00",
  ot_end:      "20:00",
  approved_by: "",
  reason:      "",
};

export default function OtEntryTab() {
  const { showToast } = useToast();
  const user            = useCurrentUser();
  const unrestricted    = isUnrestrictedUser(user);
  const canCreate       = usePermission("attendance.create");
  const effectiveBranch = getEffectiveBranch(user);

  const [form, setForm]             = useState<OvertimeCreatePayload>(EMPTY_FORM);
  const [branchInput, setBranchInput] = useState("");
  const [page, setPage]             = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError]   = useState<string | null>(null);

  const branch = unrestricted ? branchInput : effectiveBranch;

  const { data: employeeData } = useFetch<{ results: PickerEmployee[] }>(`${API.employees.list}?page_size=200`);
  const { data: approvers }    = useFetch<PickerEmployee[]>(API.employees.hrList);
  const employees = employeeData?.results ?? [];

  const { data: branchData } = useFetch<BranchOption[] | { results: BranchOption[] }>(
    unrestricted ? `${API.branches.list}?page_size=100` : null
  );
  const branches = Array.isArray(branchData) ? branchData : (branchData?.results ?? []);

  const otUrl = user
    ? `${API.attendance.overtime}?${branch ? `branch=${encodeURIComponent(branch)}&` : ""}page=${page}&page_size=20`
    : null;
  const { data: otData, loading, error, refetch } = useFetch<PaginatedOvertime>(otUrl);
  const rows = otData?.results ?? [];

  function setField<K extends keyof OvertimeCreatePayload>(key: K, value: OvertimeCreatePayload[K]) {
    setForm(prev => ({ ...prev, [key]: value }));
    setFormError(null);
  }

  async function handleSubmit() {
    if (!form.employee_id)            { setFormError("Please select an employee."); return; }
    if (!form.date)                   { setFormError("Please select a date."); return; }
    if (form.ot_end <= form.ot_start) { setFormError("OT end time must be after OT start time."); return; }

    setSubmitting(true);
    setFormError(null);
    try {
      await clientApi.post(API.attendance.overtimeCreate, form);
      showToast("Overtime entry created.", "success");
      setForm({ ...EMPTY_FORM, date: form.date });
      refetch();
    } catch (err: unknown) {
      const message = (err as { message?: string })?.message ?? "Failed to create overtime entry.";
      setFormError(message);
      showToast(message, "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Add OT form */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <i className="ti ti-plus-circle" /> Add OT Entry
          </div>
        </div>
        <div className="card-body">
          {formError && (
            <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> <span>{formError}</span></div>
          )}

          <div className="form-row cols-3">
            <div className="field-group">
              <label className="field-label">Employee</label>
              <SearchableSelect
                value={form.employee_id} onChange={v => setField("employee_id", v)}
                placeholder="Select employee…"
                options={employees.map(e => ({ value: e.employee_id, label: `${e.full_name} (${e.employee_id})` }))}
                inputClassName="field-input"
              />
            </div>
            <div className="field-group">
              <label className="field-label">Date</label>
              <input type="date" className="field-input" value={form.date} onChange={e => setField("date", e.target.value)} />
            </div>
            <div className="field-group">
              <label className="field-label">OT Type</label>
              <select className="field-input field-select" value={form.ot_type} onChange={e => setField("ot_type", e.target.value as OvertimeCreatePayload["ot_type"])}>
                <option value="regular">Regular (1.5×)</option>
                <option value="holiday">Holiday (2.0×)</option>
                <option value="weekly_off">Weekly Off (1.5×)</option>
              </select>
            </div>
          </div>
          <div className="form-row cols-3">
            <div className="field-group">
              <label className="field-label">OT Start</label>
              <input type="time" className="field-input" value={form.ot_start} onChange={e => setField("ot_start", e.target.value)} />
            </div>
            <div className="field-group">
              <label className="field-label">OT End</label>
              <input type="time" className="field-input" value={form.ot_end} onChange={e => setField("ot_end", e.target.value)} />
            </div>
            <div className="field-group">
              <label className="field-label">Approved By</label>
              <SearchableSelect
                value={form.approved_by ?? ""} onChange={v => setField("approved_by", v)}
                placeholder="Select approver…"
                options={(approvers ?? []).map(a => ({ value: a.employee_id, label: a.full_name ?? a.employee_id }))}
                inputClassName="field-input"
              />
            </div>
          </div>
          <div className="field-group mb-16">
            <label className="field-label">Reason / Work Done</label>
            <textarea
              className="field-input"
              style={{ minHeight: 72 }}
              placeholder="Describe the overtime work..."
              value={form.reason}
              onChange={e => setField("reason", e.target.value)}
            />
          </div>
          {canCreate && (
            <div style={{ textAlign: "right" }}>
              <button className="btn btn-filled" onClick={handleSubmit} disabled={submitting}>
                {submitting ? <><i className="ti ti-loader-2" /> Adding…</> : <><i className="ti ti-plus" /> Add OT Entry</>}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* OT records table */}
      <div className="card">
        <div className="card-header" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
          <div className="card-title">
            <i className="ti ti-list-details" /> OT Records
          </div>
          <BranchFilterSelect
            branches={branches}
            value={branchInput}
            onChange={value => { setBranchInput(value); setPage(1); }}
            locked={!unrestricted}
            lockedBranchName={effectiveBranch}
            width={160}
          />
        </div>
        {error && <div className="alert alert-error" style={{ margin: 16 }}><i className="ti ti-alert-circle" /> {error}</div>}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Employee</th>
                <th>Date</th>
                <th>OT Hours</th>
                <th>Type</th>
                <th>OT Amount</th>
                <th>Approved By</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={7} style={{ textAlign: "center", padding: 24, color: "var(--on-variant)" }}>Loading…</td></tr>
              )}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={7} style={{ textAlign: "center", padding: 24, color: "var(--on-variant)" }}>No overtime entries found.</td></tr>
              )}
              {rows.map(r => (
                <tr key={r.id}>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                      <div style={{ width: 30, height: 30, borderRadius: "50%", background: "rgba(124,58,237,0.1)", color: "var(--primary)", fontSize: 10, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                        {r.initials}
                      </div>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 13, color: "var(--on-bg)" }}>{r.name}</div>
                        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{r.employee_id}</div>
                      </div>
                    </div>
                  </td>
                  <td>{r.date}</td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12 }}>{r.ot_hours}</td>
                  <td>{r.ot_type}</td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12, fontWeight: 600 }}>{r.ot_amount}</td>
                  <td>{r.approved_by}</td>
                  <td>
                    <span className={`badge ${r.status.toLowerCase() === "approved" ? "badge-success" : "badge-warn"}`}>
                      {r.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {otData && otData.total_pages > 1 && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 20px", borderTop: "1px solid var(--outline-v)" }}>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Page {otData.page} of {otData.total_pages}</span>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(p => Math.max(p - 1, 1))}>
                <i className="ti ti-chevron-left" /> Prev
              </button>
              <button className="btn btn-ghost btn-sm" disabled={page >= otData.total_pages} onClick={() => setPage(p => Math.min(p + 1, otData.total_pages))}>
                Next <i className="ti ti-chevron-right" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
