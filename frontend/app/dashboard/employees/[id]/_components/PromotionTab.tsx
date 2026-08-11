"use client";

import { useState } from "react";
import { usePermission } from "@/hooks/usePermission";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { FieldOption } from "../../_data";

interface Props {
  employeeId: string;
  employeeName: string;
  currentDesignation: string;
  currentRole: string;
  desigOptions: FieldOption[];
  roleOptions: FieldOption[];
  onUpdated: (designation: string, role: string) => void;
}

interface PromotionRecord {
  id: string;
  fromDesignation: string;
  toDesignation: string;
  roleChanged: boolean;
  effectiveDate: string;
  updatedBy: string;
}

interface PromotionForm {
  designation: string;
  role: string;
  effectiveDate: string;
  remarks: string;
  confirmed: boolean;
}

const fmtDate = (d: string) =>
  new Date(d).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });

const labelFor = (options: FieldOption[], value: string) =>
  options.find(o => o.value === value)?.label ?? value;

export default function PromotionTab({
  employeeId, employeeName, currentDesignation, currentRole, desigOptions, roleOptions, onUpdated,
}: Props) {
  const canEdit = usePermission("employees.edit");
  const currentUser = useCurrentUser();

  const [history, setHistory] = useState<PromotionRecord[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [form, setForm] = useState<PromotionForm>({
    designation: currentDesignation, role: currentRole, effectiveDate: "", remarks: "", confirmed: false,
  });

  const isElevated = form.role !== currentRole;
  const hasChange = form.designation !== currentDesignation || form.role !== currentRole;

  function openModal() {
    setForm({
      designation: currentDesignation,
      role: currentRole,
      effectiveDate: new Date().toISOString().split("T")[0],
      remarks: "",
      confirmed: false,
    });
    setFormError(null);
    setShowModal(true);
  }

  async function submit() {
    if (!hasChange) {
      setFormError("Choose a new designation or role before submitting.");
      return;
    }
    if (isElevated && !form.confirmed) {
      setFormError("Confirm the role change before submitting.");
      return;
    }
    if (!form.effectiveDate) {
      setFormError("Effective date is required.");
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      await clientApi.put(API.employees.detail(employeeId), {
        designation: form.designation,
        role: form.role,
      });
      setHistory(h => [
        {
          id: `${employeeId}-${Date.now()}`,
          fromDesignation: currentDesignation || "—",
          toDesignation: form.designation,
          roleChanged: isElevated,
          effectiveDate: form.effectiveDate,
          updatedBy: currentUser?.name ?? "—",
        },
        ...h,
      ]);
      onUpdated(form.designation, form.role);
      setShowModal(false);
      setSuccessMsg(
        isElevated
          ? "Designation and role updated. New access applies at the employee's next login."
          : "Designation updated successfully."
      );
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Failed to update. Please try again.";
      setFormError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      {successMsg && (
        <div className="alert alert-success"><i className="ti ti-circle-check" />{successMsg}</div>
      )}

      <div className="card">
        <div className="card-header">
          <span className="card-title">Current Designation</span>
          {canEdit && (
            <button className="btn btn-filled btn-sm" onClick={openModal}>
              <i className="ti ti-award" /> Promote Employee
            </button>
          )}
        </div>
        <div className="card-body">
          <div className="text-[20px] font-semibold">{currentDesignation || "—"}</div>
          <div className="text-[13px] text-muted mt-1">
            {employeeName} · {labelFor(roleOptions, currentRole)}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">Promotion History</span>
        </div>
        {history.length === 0 ? (
          <div className="empty-state">
            <i className="ti ti-award" />
            <h3>No promotions yet</h3>
            <p>Changes made here will be listed for this session.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Change</th>
                  <th>Effective date</th>
                  <th>Updated by</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {history.map(h => (
                  <tr key={h.id}>
                    <td>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span>{h.fromDesignation}</span>
                        <i className="ti ti-arrow-right text-muted" />
                        <span className="font-medium">{h.toDesignation}</span>
                        {h.roleChanged && <span className="badge badge-warn">Role change</span>}
                      </div>
                    </td>
                    <td className="tabular-nums">{fmtDate(h.effectiveDate)}</td>
                    <td>{h.updatedBy}</td>
                    <td><span className="badge badge-success">Applied</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showModal && (
        <div className="modal-overlay open" onClick={e => { if (e.target === e.currentTarget) setShowModal(false); }}>
          <div className="modal">
            <div className="modal-header">
              <span className="modal-title">Promote Employee</span>
              <button className="modal-close" onClick={() => setShowModal(false)}><i className="ti ti-x" /></button>
            </div>
            <div className="modal-body flex flex-col gap-4">
              {formError && <div className="alert alert-error">{formError}</div>}

              <div className="field-group">
                <label className="field-label">New designation</label>
                <select
                  className="field-input field-select"
                  value={form.designation}
                  onChange={e => setForm(f => ({ ...f, designation: e.target.value }))}
                >
                  {!desigOptions.find(o => o.value === currentDesignation) && (
                    <option value={currentDesignation}>{currentDesignation}</option>
                  )}
                  {desigOptions.map(d => <option key={d.value} value={d.value}>{d.label}</option>)}
                </select>
              </div>

              <div className="field-group">
                <label className="field-label">System role</label>
                <select
                  className="field-input field-select"
                  value={form.role}
                  onChange={e => setForm(f => ({ ...f, role: e.target.value, confirmed: false }))}
                >
                  {!roleOptions.find(o => o.value === currentRole) && (
                    <option value={currentRole}>{currentRole}</option>
                  )}
                  {roleOptions.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
              </div>

              <div className="field-group">
                <label className="field-label">Effective date</label>
                <input
                  className="field-input"
                  type="date"
                  value={form.effectiveDate}
                  onChange={e => setForm(f => ({ ...f, effectiveDate: e.target.value }))}
                />
              </div>

              <div className="field-group">
                <label className="field-label">Remarks <span className="text-muted">(optional)</span></label>
                <textarea
                  className="field-input"
                  placeholder="Reason for promotion"
                  value={form.remarks}
                  onChange={e => setForm(f => ({ ...f, remarks: e.target.value }))}
                />
              </div>

              {isElevated && (
                <>
                  <div className="alert alert-warn">
                    <i className="ti ti-shield-lock" />
                    This grants {labelFor(roleOptions, form.role)} access. New permissions apply at the
                    employee&apos;s next login.
                  </div>
                  <label className="flex items-start gap-2 text-[13px]">
                    <input
                      type="checkbox"
                      className="mt-0.5"
                      checked={form.confirmed}
                      onChange={e => setForm(f => ({ ...f, confirmed: e.target.checked }))}
                    />
                    I confirm this role change and its access impact.
                  </label>
                </>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setShowModal(false)} disabled={submitting}>
                Cancel
              </button>
              <button className="btn btn-filled" onClick={submit} disabled={submitting || !hasChange}>
                {submitting ? <><i className="ti ti-loader-2 spin" /> Updating…</> : "Update Employee"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
