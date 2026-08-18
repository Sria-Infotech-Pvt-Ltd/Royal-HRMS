"use client";

import { useState } from "react";
import Modal from "@/components/Modal";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { API } from "@/lib/api/endpoints";
import type { BonusEntry, EmployeePayslip, EmployeeReferralSummary } from "@/types/payroll";

interface Props {
  payslip: EmployeePayslip;
  referralSummary: EmployeeReferralSummary | null;
  onSaved: () => void;
  onClose: () => void;
}

const BONUS_TYPES = ["Annual", "Performance", "Referral", "Festival", "Retention", "Ad-hoc"];

const fmt = (n: string | number) =>
  `₹${Number(n).toLocaleString("en-IN", { minimumFractionDigits: 0 })}`;

function emptyEntry(): BonusEntry {
  return { type: "Performance", amount: "", note: "" };
}

export default function BonusEditModal({ payslip, referralSummary, onSaved, onClose }: Props) {
  const { showToast } = useToast();
  const referrals = referralSummary?.referral_bonuses ?? [];

  const [entries, setEntries] = useState<BonusEntry[]>(
    () => payslip.bonus_breakdown?.length ? payslip.bonus_breakdown : []
  );
  const [saving, setSaving] = useState(false);

  function addEntry() {
    setEntries(prev => [...prev, emptyEntry()]);
  }

  function removeEntry(idx: number) {
    setEntries(prev => prev.filter((_, i) => i !== idx));
  }

  function updateEntry(idx: number, field: keyof BonusEntry, value: string) {
    setEntries(prev => prev.map((e, i) => i === idx ? { ...e, [field]: value } : e));
  }

  function importReferral(bonus: { bonus_amount: string; candidate_name: string }) {
    setEntries(prev => [
      ...prev,
      { type: "Referral", amount: bonus.bonus_amount, note: `Referral: ${bonus.candidate_name}` },
    ]);
  }

  const total = entries.reduce((s, e) => s + (Number(e.amount) || 0), 0);

  async function handleSave() {
    const valid = entries.filter(e => Number(e.amount) > 0);
    setSaving(true);
    try {
      await clientApi.patch(API.payroll.payslipReimbBonus(payslip.id), {
        bonus_breakdown: valid,
      });
      showToast("Bonuses updated.", "success");
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
          <i className="ti ti-gift" style={{ marginRight: 6 }} />
          Bonuses — {payslip.employee_name}
        </>
      }
      onClose={onClose}
      maxWidth={560}
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
        {/* Referral suggestions */}
        {referrals.length > 0 && (
          <div style={{ background: "var(--bg-low)", borderRadius: 8, padding: "10px 14px" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: ".04em", marginBottom: 8 }}>
              <i className="ti ti-user-plus" style={{ marginRight: 4 }} /> Pending Referral Bonuses
            </div>
            {referrals.map(r => (
              <div key={r.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                <div style={{ fontSize: 13 }}>
                  <span style={{ fontWeight: 600 }}>{fmt(r.bonus_amount)}</span>
                  <span style={{ color: "var(--on-variant)", marginLeft: 8, fontSize: 12 }}>for {r.candidate_name}</span>
                </div>
                <button className="btn btn-ghost btn-sm" onClick={() => importReferral(r)}>
                  <i className="ti ti-plus" /> Add
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Bonus entries */}
        {entries.length === 0 ? (
          <div style={{ textAlign: "center", padding: "20px 0", color: "var(--on-variant)", fontSize: 13 }}>
            No bonus entries yet. Click &quot;Add Bonus&quot; below.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {entries.map((entry, idx) => (
              <div key={idx} style={{ display: "grid", gridTemplateColumns: "1fr 120px 1fr auto", gap: 8, alignItems: "center" }}>
                <select
                  className="field-input"
                  value={entry.type}
                  onChange={e => updateEntry(idx, "type", e.target.value)}
                >
                  {BONUS_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
                <input
                  type="number"
                  className="field-input"
                  placeholder="Amount"
                  min={0}
                  step={500}
                  value={entry.amount}
                  onChange={e => updateEntry(idx, "amount", e.target.value)}
                />
                <input
                  type="text"
                  className="field-input"
                  placeholder="Note (optional)"
                  maxLength={200}
                  value={entry.note}
                  onChange={e => updateEntry(idx, "note", e.target.value)}
                />
                <button className="btn btn-ghost btn-sm" onClick={() => removeEntry(idx)} style={{ color: "var(--error)" }}>
                  <i className="ti ti-trash" />
                </button>
              </div>
            ))}
          </div>
        )}

        <button className="btn btn-ghost btn-sm" onClick={addEntry} style={{ alignSelf: "flex-start" }}>
          <i className="ti ti-plus" /> Add Bonus
        </button>

        {entries.length > 0 && (
          <div style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderTop: "1px solid var(--outline-v)", fontWeight: 700 }}>
            <span>Total bonus</span>
            <span style={{ color: "var(--warn)" }}>{fmt(total)}</span>
          </div>
        )}
      </div>
    </Modal>
  );
}
