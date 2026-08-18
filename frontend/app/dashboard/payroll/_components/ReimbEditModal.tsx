"use client";

import { useState } from "react";
import Modal from "@/components/Modal";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { API } from "@/lib/api/endpoints";
import type { EmployeeExpenseSummary, EmployeePayslip, ExpenseItem } from "@/types/payroll";

interface Props {
  payslip: EmployeePayslip;
  summary: EmployeeExpenseSummary | null;
  onSaved: () => void;
  onClose: () => void;
}

const CATEGORY_LABEL: Record<string, string> = {
  travel: "Travel", meals: "Meals", equipment: "Equipment", other: "Other",
};

const fmt = (n: string | number) =>
  `₹${Number(n).toLocaleString("en-IN", { minimumFractionDigits: 0 })}`;

export default function ReimbEditModal({ payslip, summary, onSaved, onClose }: Props) {
  const { showToast } = useToast();
  const expenses: ExpenseItem[] = summary?.expenses ?? [];

  // Pre-check already-included expenses
  const [checked, setChecked] = useState<Set<string>>(
    () => new Set(expenses.filter(e => e.already_included).map(e => e.id))
  );
  const [manualMode, setManualMode] = useState(expenses.length === 0);
  const [manualAmount, setManualAmount] = useState(payslip.reimbursements);
  const [saving, setSaving] = useState(false);

  function toggle(id: string) {
    setChecked(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  const checkedTotal = expenses
    .filter(e => checked.has(e.id))
    .reduce((s, e) => s + Number(e.amount), 0);

  async function handleSave() {
    setSaving(true);
    try {
      const payload = manualMode
        ? { reimbursements: manualAmount }
        : { expense_ids: [...checked] };
      await clientApi.patch(API.payroll.payslipReimbBonus(payslip.id), payload);
      showToast("Reimbursements updated.", "success");
      onSaved();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
        ?? "Failed to save.";
      showToast(msg, "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      title={
        <>
          <i className="ti ti-receipt" style={{ marginRight: 6 }} />
          Reimbursements — {payslip.employee_name}
        </>
      }
      onClose={onClose}
      maxWidth={520}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-filled" onClick={handleSave} disabled={saving}>
            {saving
              ? <><i className="ti ti-loader-2 animate-spin" /> Saving…</>
              : <><i className="ti ti-check" /> Save</>
            }
          </button>
        </>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {/* Mode toggle */}
        {expenses.length > 0 && (
          <div style={{ display: "flex", gap: 8 }}>
            <button
              className={`btn btn-sm ${!manualMode ? "btn-filled" : "btn-ghost"}`}
              onClick={() => setManualMode(false)}
            >
              <i className="ti ti-list-check" /> From expense claims
            </button>
            <button
              className={`btn btn-sm ${manualMode ? "btn-filled" : "btn-ghost"}`}
              onClick={() => setManualMode(true)}
            >
              <i className="ti ti-pencil" /> Enter manually
            </button>
          </div>
        )}

        {!manualMode && expenses.length > 0 && (
          <>
            <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
              Select expense claims to disburse in this payroll run.
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 280, overflowY: "auto" }}>
              {expenses.map(exp => (
                <label
                  key={exp.id}
                  style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "10px 12px", border: `1.5px solid ${checked.has(exp.id) ? "var(--primary)" : "var(--outline-v)"}`, borderRadius: 8, cursor: "pointer", background: checked.has(exp.id) ? "rgba(var(--primary-rgb,59,130,246),0.04)" : "transparent" }}
                >
                  <input
                    type="checkbox"
                    checked={checked.has(exp.id)}
                    onChange={() => toggle(exp.id)}
                    style={{ marginTop: 2, accentColor: "var(--primary)", flexShrink: 0 }}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: 13 }}>{exp.title}</div>
                    <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
                      {CATEGORY_LABEL[exp.category] ?? exp.category} · {exp.expense_date}
                    </div>
                  </div>
                  <div style={{ fontWeight: 700, fontSize: 13, color: "var(--info)", flexShrink: 0 }}>
                    {fmt(exp.amount)}
                  </div>
                </label>
              ))}
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderTop: "1px solid var(--outline-v)", fontWeight: 700 }}>
              <span>Total selected</span>
              <span style={{ color: "var(--info)" }}>{fmt(checkedTotal)}</span>
            </div>
          </>
        )}

        {(manualMode || expenses.length === 0) && (
          <div>
            {expenses.length === 0 && (
              <div className="alert alert-info" style={{ marginBottom: 12 }}>
                <i className="ti ti-info-circle" /> No approved expense claims found for this employee.
              </div>
            )}
            <label className="field-label">Reimbursement Amount (₹)</label>
            <input
              type="number"
              className="field-input"
              min={0}
              step={100}
              value={manualAmount}
              onChange={e => setManualAmount(e.target.value)}
            />
          </div>
        )}
      </div>
    </Modal>
  );
}
