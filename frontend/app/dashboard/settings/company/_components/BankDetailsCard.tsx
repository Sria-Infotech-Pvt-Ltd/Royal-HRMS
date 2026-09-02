"use client";

import type { CompanySectionProps } from "@/types/company";
import ProfileCard from "./ProfileCard";
import { BANK_ACCOUNT_TYPE_OPTIONS, resolveIfsc } from "../_data";

export default function BankDetailsCard({ form, canEdit, onFieldChange, collapsed, onToggleCollapse }: CompanySectionProps) {
  const ifsc = resolveIfsc(form.bank_ifsc);

  return (
    <ProfileCard icon="ti-building-bank" title="Bank details" subtitle="Used for payouts and on invoices. IFSC resolves bank and branch." collapsed={collapsed} onToggleCollapse={onToggleCollapse}>
      <div className="form-row cols-2">
        <div className="field-group">
          <label className="field-label">Account Holder <span style={{ color: "var(--error)" }}>*</span></label>
          <input
            className="field-input"
            value={form.bank_account_holder}
            disabled={!canEdit}
            onChange={e => onFieldChange("bank_account_holder", e.target.value)}
          />
        </div>
        <div className="field-group">
          <label className="field-label">Account Number <span style={{ color: "var(--error)" }}>*</span></label>
          <input
            className="field-input"
            value={form.bank_account_number}
            disabled={!canEdit}
            onChange={e => onFieldChange("bank_account_number", e.target.value)}
          />
        </div>
        <div className="field-group">
          <label className="field-label">IFSC <span style={{ color: "var(--error)" }}>*</span></label>
          <input
            className="field-input"
            value={form.bank_ifsc}
            disabled={!canEdit}
            onChange={e => onFieldChange("bank_ifsc", e.target.value.toUpperCase())}
            maxLength={11}
          />
        </div>
        <div className="field-group">
          <label className="field-label">Account Type</label>
          <select
            className="field-input"
            value={form.bank_account_type}
            disabled={!canEdit}
            onChange={e => onFieldChange("bank_account_type", e.target.value)}
          >
            <option value="">Select…</option>
            {BANK_ACCOUNT_TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>
      {ifsc && (
        <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          <div style={{
            padding: "6px 12px", borderRadius: 6, fontSize: 11,
            background: "var(--bg-low)", border: "1px solid var(--outline-v)",
          }}>
            <div style={{ color: "var(--on-variant)", marginBottom: 2 }}>Bank</div>
            <div style={{ fontWeight: 600 }}>{ifsc.bank ?? "Unrecognized bank code"}</div>
          </div>
          <div style={{
            padding: "6px 12px", borderRadius: 6, fontSize: 11,
            background: "var(--bg-low)", border: "1px solid var(--outline-v)",
          }}>
            <div style={{ color: "var(--on-variant)", marginBottom: 2 }}>Branch code</div>
            <div style={{ fontWeight: 600 }}>{ifsc.branchCode}</div>
          </div>
        </div>
      )}
    </ProfileCard>
  );
}
