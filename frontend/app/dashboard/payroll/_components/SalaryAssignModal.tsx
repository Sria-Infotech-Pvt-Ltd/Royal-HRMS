"use client";

// Assign / update one employee's annual CTC. Empty or non-positive input is refused with a message (never silently),
// and the server says "no change" when the salary is already what is being saved.

import { useState } from "react";
import Modal from "@/components/Modal";
import DateInput from "@/components/shared/DateInput";
import type { SalaryStructureListItem } from "@/types/payroll";
import type { SalarySetupRow } from "@/types/salarySetup";

interface Props {
  employee: SalarySetupRow;
  structures: SalaryStructureListItem[];
  onClose: () => void;
  /** Throws a readable error to show in the dialog; resolves when the salary is saved. */
  onSave: (values: { annual_ctc: string; effective_from: string; salary_structure: string | null }) => Promise<void>;
}

const formatRupees = (amount: number | string) => `₹${Number(amount).toLocaleString("en-IN", { minimumFractionDigits: 0 })}`;

export default function SalaryAssignModal({ employee, structures, onClose, onSave }: Props) {
  const current = employee.salary;
  const [annualCtc, setAnnualCtc] = useState(current ? String(Math.round(Number(current.annual_ctc))) : "");
  const [effectiveFrom, setEffectiveFrom] = useState(current?.effective_from ?? new Date().toISOString().split("T")[0]);
  const [structure, setStructure] = useState(current?.salary_structure ?? "");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    const amount = Number(annualCtc);
    if (annualCtc.trim() === "") { setError("Enter the annual CTC."); return; }
    if (!Number.isFinite(amount) || amount <= 0) { setError("Annual CTC must be a number greater than 0."); return; }
    if (!effectiveFrom) { setError("Choose the date this takes effect."); return; }
    setError(null);
    setIsSaving(true);
    try {
      await onSave({ annual_ctc: annualCtc, effective_from: effectiveFrom, salary_structure: structure || null });
    } catch (err: unknown) {
      setError((err as { message?: string })?.message || "Failed to save the salary.");
      setIsSaving(false);
    }
  }

  return (
    <Modal
      title={<><i className="ti ti-currency-rupee" style={{ marginRight: 8 }} />{current ? "Update CTC" : "Assign CTC"} — {employee.full_name}</>}
      onClose={onClose}
      maxWidth={480}
      footer={
        <>
          <button className="btn btn-ghost" type="button" onClick={onClose}>Cancel</button>
          <button className="btn btn-filled" type="button" onClick={submit} disabled={isSaving}>
            {isSaving ? <><i className="ti ti-loader-2 animate-spin" /> Saving…</> : <><i className="ti ti-check" /> Save CTC</>}
          </button>
        </>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {error && <div className="alert alert-error" role="alert" style={{ marginBottom: 0 }}><i className="ti ti-alert-circle" /><span>{error}</span></div>}
        <div style={{ padding: "10px 14px", background: "var(--bg-low)", borderRadius: "var(--radius)", fontSize: 12, color: "var(--on-variant)" }}>
          <strong>{employee.employee_id}</strong> · {employee.department || "—"} · {employee.branch || "—"}
        </div>
        {current && (
          <div className="alert alert-info" style={{ marginBottom: 0 }}>
            <i className="ti ti-info-circle" />
            <span>Current CTC: <strong>{formatRupees(current.annual_ctc)}/year</strong> (effective {current.effective_from}). Saving a different amount adds a new record; saving the same amount changes nothing.</span>
          </div>
        )}
        <div className="form-row cols-2">
          <div className="field-group">
            <label className="field-label">Annual CTC (₹) *</label>
            <input type="number" className="field-input" min={0} step={1000} placeholder="e.g. 600000" value={annualCtc} onChange={event => setAnnualCtc(event.target.value)} />
            {annualCtc && Number(annualCtc) > 0 && <span style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 4, display: "block" }}>Monthly: {formatRupees(Number(annualCtc) / 12)}</span>}
          </div>
          <div className="field-group">
            <label className="field-label">Effective From *</label>
            <DateInput className="field-input" value={effectiveFrom} onChange={setEffectiveFrom} />
          </div>
        </div>
        <div className="field-group">
          <label className="field-label">Salary Structure Override</label>
          <select className="field-input field-select" value={structure} onChange={event => setStructure(event.target.value)}>
            <option value="">— Use Company Code / company default —</option>
            {structures.filter(item => item.is_active).map(item => <option key={item.id} value={item.id}>{item.name}{item.is_default ? " (Default)" : ""}</option>)}
          </select>
        </div>
      </div>
    </Modal>
  );
}
